import csv
import logging

from decimal import Decimal, ROUND_DOWN
from pathlib import Path
from typing import Final

from dateutil.parser import parse as parse_timestamp

from investir.const import MIN_TIMESTAMP
from investir.utils import read_decimal, dict2str
from investir.exceptions import (
    ParserError,
    CalculatedAmountError,
    FeeError,
    OrderTooOldError,
)
from investir.config import config
from investir.parser import Parser, ParsingResult
from investir.typing import Ticker
from investir.transaction import (
    Order,
    Acquisition,
    Disposal,
    Dividend,
    Transfer,
    Interest,
)
from investir.utils import raise_or_warn


logger = logging.getLogger(__name__)


class FreetradeParser(Parser):
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

    @staticmethod
    def name() -> str:
        return "Freetrade"

    def can_parse(self) -> bool:
        with self._csv_file.open(encoding="utf-8") as file:
            reader = csv.DictReader(file)
            if reader.fieldnames:
                return tuple(reader.fieldnames) == self.FIELDS

        return False

    def parse(self) -> ParsingResult:
        parse_fn = {
            "ORDER": self._parse_order,
            "DIVIDEND": self._parse_dividend,
            "TOP_UP": self._parse_transfer,
            "WITHDRAW": self._parse_transfer,
            "INTEREST_FROM_CASH": self._parse_interest,
            "MONTHLY_STATEMENT": lambda _: None,
        }

        with self._csv_file.open(encoding="utf-8") as file:
            reader = csv.DictReader(file)

            # Freetrade transactions are ordered from most recent to
            # oldest but we want the order ID to increase from the
            # oldest to the most recent.
            rows = reversed(list(reader))

            for row in rows:
                tr_type = row["Type"]
                if fn := parse_fn.get(tr_type):
                    if (
                        row["Type"] != "MONTHLY_STATEMENT"
                        and row["Account Currency"] != "GBP"
                    ):
                        raise ParserError(
                            self._csv_file.name,
                            "Only 'GBP' is supported for the 'Account currency' field",
                        )
                    fn(row)
                else:
                    raise_or_warn(
                        ParserError(
                            self._csv_file.name,
                            f"Unrecognised value for `Type` field: {tr_type}",
                        )
                    )

        return ParsingResult(
            self._orders, self._dividends, self._transfers, self._interest
        )

    def _parse_order(self, row: dict[str, str]) -> None:
        action = row["Buy / Sell"]
        timestamp = parse_timestamp(row["Timestamp"])
        total_amount = Decimal(row["Total Amount"])
        ticker = row["Ticker"]
        price = Decimal(row["Price per Share in Account Currency"])
        quantity = Decimal(row["Quantity"])
        order_id = row["Order ID"]
        stamp_duty = read_decimal(row["Stamp Duty"])
        fx_fee_amount = read_decimal(row["FX Fee Amount"])

        if timestamp < MIN_TIMESTAMP:
            raise OrderTooOldError(row)

        if stamp_duty and fx_fee_amount:
            raise FeeError(self._csv_file.name)

        order_class: type[Order] = Acquisition
        fees = stamp_duty + fx_fee_amount

        if action == "SELL":
            order_class = Disposal
            fees *= -1

        calculated_amount = round(price * quantity + fees, 2)
        if calculated_amount != total_amount:
            raise_or_warn(
                CalculatedAmountError(
                    self._csv_file.name, calculated_amount, total_amount
                )
            )

        if config.include_fx_fees:
            allowable_fees = abs(fees)
        else:
            allowable_fees = stamp_duty

        self._orders.append(
            order_class(
                timestamp,
                amount=total_amount - fees,
                ticker=Ticker(ticker),
                quantity=quantity,
                fees=allowable_fees,
                order_id=order_id,
            )
        )

        logging.debug("Parsed row %s as %s\n", dict2str(row), self._orders[-1])

    def _parse_dividend(self, row: dict[str, str]):
        timestamp = parse_timestamp(row["Timestamp"])
        total_amount = Decimal(row["Total Amount"])
        ticker = row["Ticker"]
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
        if abs(total_amount - calculated_ta) > Decimal("0.01"):
            raise_or_warn(
                CalculatedAmountError(self._csv_file.name, calculated_ta, total_amount)
            )

        self._dividends.append(
            Dividend(
                timestamp,
                total_amount,
                ticker=Ticker(ticker),
                withheld=withheld_tax_amount * base_fx_rate,
            )
        )

        logging.debug("Parsed row %s as %s\n", dict2str(row), self._dividends[-1])

    def _parse_transfer(self, row: dict[str, str]):
        timestamp = parse_timestamp(row["Timestamp"])
        tr_type = row["Type"]
        total_amount = Decimal(row["Total Amount"])

        if tr_type == "WITHDRAW":
            total_amount *= -1

        self._transfers.append(Transfer(timestamp, total_amount))

        logging.debug("Parsed row %s as %s\n", dict2str(row), self._transfers[-1])

    def _parse_interest(self, row: dict[str, str]):
        timestamp = parse_timestamp(row["Timestamp"])
        total_amount = Decimal(row["Total Amount"])

        self._interest.append(Interest(timestamp, total_amount))

        logging.debug("Parsed row %s as %s\n", dict2str(row), self._interest[-1])
