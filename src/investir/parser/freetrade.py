import csv
import logging
from collections.abc import Mapping
from datetime import datetime
from decimal import ROUND_DOWN, Decimal
from pathlib import Path
from typing import Final

from dateutil.parser import parse as parse_timestamp
from moneyed import Money

from investir.config import config
from investir.const import MIN_TIMESTAMP
from investir.exceptions import (
    CalculatedAmountError,
    FeesError,
    OrderDateError,
    TransactionTypeError,
)
from investir.parser.factory import ParserFactory
from investir.parser.types import ParsingResult
from investir.transaction import (
    Acquisition,
    Disposal,
    Dividend,
    Interest,
    Order,
    Transfer,
)
from investir.typing import ISIN, Ticker
from investir.utils import dict2str, raise_or_warn, read_decimal

logger = logging.getLogger(__name__)


@ParserFactory.register("Freetrade")
class FreetradeParser:
    FIELDS: Final = (
        "Title",
        "Type",
        "Timestamp",
        "Account Currency",
        "Total Amount",
        "Buy / Sell",
        "Ticker",
        "ISIN",
        "Price per Share in Account Currency",
        "Stamp Duty",
        "Quantity",
        "Venue",
        "Order ID",
        "Order Type",
        "Instrument Currency",
        "Total Shares Amount",
        "Price per Share",
        "FX Rate",
        "Base FX Rate",
        "FX Fee (BPS)",
        "FX Fee Amount",
        "Dividend Ex Date",
        "Dividend Pay Date",
        "Dividend Eligible Quantity",
        "Dividend Amount Per Share",
        "Dividend Gross Distribution Amount",
        "Dividend Net Distribution Amount",
        "Dividend Withheld Tax Percentage",
        "Dividend Withheld Tax Amount",
    )

    def __init__(self, csv_file: Path) -> None:
        self._csv_file = csv_file
        self._orders: list[Order] = []
        self._dividends: list[Dividend] = []
        self._transfers: list[Transfer] = []
        self._interest: list[Interest] = []

    def can_parse(self) -> bool:
        with self._csv_file.open(encoding="utf-8") as file:
            reader = csv.DictReader(file)
            return tuple(reader.fieldnames or []) == self.FIELDS

    def parse(self) -> ParsingResult:
        parse_fn = {
            "ORDER": self._parse_order,
            "DIVIDEND": self._parse_dividend,
            "TOP_UP": self._parse_transfer,
            "WITHDRAWAL": self._parse_transfer,
            "INTEREST_FROM_CASH": self._parse_interest,
            "MONTHLY_STATEMENT": None,
            "TAX_CERTIFICATE": None,
        }

        with self._csv_file.open(encoding="utf-8") as file:
            reader = csv.DictReader(file)

            # Freetrade transactions are ordered from most recent to
            # oldest but we want the order ID to increase from the
            # oldest to the most recent.
            rows = reversed(list(reader))

            for row in rows:
                tr_type = row["Type"]

                if tr_type not in parse_fn:
                    raise_or_warn(TransactionTypeError(self._csv_file, row, tr_type))
                    continue

                if fn := parse_fn.get(tr_type):
                    timestamp = parse_timestamp(row["Timestamp"])
                    total = Money(Decimal(row["Total Amount"]), row["Account Currency"])

                    fn(row, tr_type, timestamp, total)

        return ParsingResult(
            self._orders, self._dividends, self._transfers, self._interest
        )

    def _parse_order(
        self,
        row: Mapping[str, str],
        tr_type: str,
        timestamp: datetime,
        total: Money,
    ) -> None:
        title = row["Title"]
        action = row["Buy / Sell"]
        ticker = row["Ticker"]
        isin = row["ISIN"]
        price = Decimal(row["Price per Share in Account Currency"])
        quantity = Decimal(row["Quantity"])
        order_id = row["Order ID"]
        stamp_duty = read_decimal(row["Stamp Duty"])
        fx_fee_amount = read_decimal(row["FX Fee Amount"])

        if action not in ("BUY", "SELL"):
            raise TransactionTypeError(self._csv_file, row, action)

        if timestamp < MIN_TIMESTAMP:
            raise OrderDateError(self._csv_file, row)

        if stamp_duty and fx_fee_amount:
            raise FeesError(self._csv_file, row, "Stamp Duty", "FX Fee Amount")

        order_class: type[Order] = Acquisition
        fees = stamp_duty + fx_fee_amount

        if action == "SELL":
            order_class = Disposal
            fees *= -1

        calculated_amount = round(price * quantity + fees, 2)
        if calculated_amount != total.amount:
            raise_or_warn(
                CalculatedAmountError(
                    self._csv_file, row, total.amount, calculated_amount
                )
            )

        allowable_fees = abs(fees)
        if not config.include_fx_fees:
            allowable_fees -= fx_fee_amount

        self._orders.append(
            order_class(
                timestamp,
                isin=ISIN(isin),
                ticker=Ticker(ticker),
                name=title,
                total=Money(total.amount - fees, total.currency),
                quantity=quantity,
                fees=Money(allowable_fees, total.currency),
                tr_id=order_id,
            )
        )

        logger.debug("Parsed row %s as %s\n", dict2str(row), self._orders[-1])

    def _parse_dividend(
        self,
        row: Mapping[str, str],
        tr_type: str,
        timestamp: datetime,
        total: Money,
    ):
        title = row["Title"]
        ticker = row["Ticker"]
        isin = row["ISIN"]
        base_fx_rate = read_decimal(row["Base FX Rate"], Decimal("1.0"))
        eligible_quantity = Decimal(row["Dividend Eligible Quantity"])
        amount_per_share = Decimal(row["Dividend Amount Per Share"])
        withheld_tax_percentage = Decimal(row["Dividend Withheld Tax Percentage"])
        withheld_tax_amount = Decimal(row["Dividend Withheld Tax Amount"])

        calculated_ta = (
            amount_per_share
            * eligible_quantity
            * ((Decimal("100") - withheld_tax_percentage) / 100)
            * base_fx_rate
        )

        calculated_ta = calculated_ta.quantize(Decimal("1.00"), rounding=ROUND_DOWN)

        # Freetrade does not seem to use a consistent method for rounding dividends.
        # Thus, allow the calculated amount to differ by one pence.
        # https://community.freetrade.io/t/dividend-amount-off-by-one-penny/71806/7
        if abs(total.amount - calculated_ta) > Decimal("0.01"):
            raise_or_warn(
                CalculatedAmountError(self._csv_file, row, total.amount, calculated_ta)
            )

        self._dividends.append(
            Dividend(
                timestamp,
                isin=ISIN(isin),
                ticker=Ticker(ticker),
                name=title,
                total=total,
                withheld=Money(withheld_tax_amount * base_fx_rate, total.currency),
            )
        )

        logger.debug("Parsed row %s as %s\n", dict2str(row), self._dividends[-1])

    def _parse_transfer(
        self,
        row: Mapping[str, str],
        tr_type: str,
        timestamp: datetime,
        total: Money,
    ):
        if tr_type == "WITHDRAWAL":
            total = -abs(total)

        self._transfers.append(Transfer(timestamp, total))

        logger.debug("Parsed row %s as %s\n", dict2str(row), self._transfers[-1])

    def _parse_interest(
        self,
        row: Mapping[str, str],
        tr_type: str,
        timestamp: datetime,
        total: Money,
    ):
        self._interest.append(Interest(timestamp, total))

        logger.debug("Parsed row %s as %s\n", dict2str(row), self._interest[-1])
