import csv
import logging
from collections.abc import Mapping
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Final

from dateutil.parser import parse as parse_timestamp
from moneyed import Money, get_currency

from investir.config import config
from investir.const import MIN_TIMESTAMP
from investir.exceptions import (
    CalculatedAmountError,
    FeesError,
    OrderDateError,
    ParseError,
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
from investir.utils import dict2str, raise_or_warn, read_decimal, read_sterling

logger = logging.getLogger(__name__)


@ParserFactory.register("Trading212")
class Trading212Parser:
    INITIAL_FIELDS: Final = (
        "Action",
        "Time",
    )

    MANDATORY_FIELDS: Final = (
        "Total",
        "Currency (Total)",
        "Notes",
        "ID",
    )

    OPTIONAL_FIELDS: Final = (
        "ISIN",
        "Ticker",
        "Name",
        "No. of shares",
        "Price / share",
        "Currency (Price / share)",
        "Exchange rate",
        "Currency (Result)",
        "Result",
        "Withholding tax",
        "Currency (Withholding tax)",
        "Currency conversion from amount",
        "Currency (Currency conversion from amount)",
        "Currency conversion to amount",
        "Currency (Currency conversion to amount)",
        "Currency conversion fee",
        "Currency (Currency conversion fee)",
        "Finra fee (GBP)",
        "Stamp duty (GBP)",
        "Merchant name",
        "Merchant category",
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
            fieldnames = reader.fieldnames or []
            idx = len(self.INITIAL_FIELDS)
            fields1 = fieldnames[:idx]
            fields2 = fieldnames[idx:]

            if tuple(fields1) != self.INITIAL_FIELDS:
                return False

            if any(f not in fields2 for f in self.MANDATORY_FIELDS):
                return False

            if any(
                f not in self.MANDATORY_FIELDS and f not in self.OPTIONAL_FIELDS
                for f in fields2
            ):
                return False

        return True

    def parse(self) -> ParsingResult:
        parse_fn = {
            "Market buy": self._parse_order,
            "Limit buy": self._parse_order,
            "Market sell": self._parse_order,
            "Limit sell": self._parse_order,
            "Dividend (Ordinary)": self._parse_dividend,
            "Dividend (Dividend)": self._parse_dividend,
            "Dividend (Dividends paid by us corporations)": self._parse_dividend,
            "Dividend (Dividends paid by foreign corporations)": self._parse_dividend,
            "Deposit": self._parse_transfer,
            "Withdrawal": self._parse_transfer,
            "Interest on cash": self._parse_interest,
            "Card debit": None,
            "Spending cashback": None,
            "Currency conversion": None,
        }

        with self._csv_file.open(encoding="utf-8") as file:
            for row in csv.DictReader(file):
                tr_type = row["Action"]

                if tr_type not in parse_fn:
                    raise_or_warn(TransactionTypeError(self._csv_file, row, tr_type))
                    continue

                if fn := parse_fn.get(tr_type):
                    timestamp = parse_timestamp(row["Time"])
                    tr_id = row["ID"]
                    total_amount = Decimal(row["Total"])
                    total_currency = row["Currency (Total)"]

                    fn(row, tr_type, timestamp, tr_id, total_amount, total_currency)

        return ParsingResult(
            self._orders, self._dividends, self._transfers, self._interest
        )

    def _parse_order(
        self,
        row: Mapping[str, str],
        tr_type: str,
        timestamp: datetime,
        tr_id: str,
        total_amount: Decimal,
        total_currency: str,
    ) -> None:
        isin = row["ISIN"]
        ticker = row["Ticker"]
        name = row["Name"]
        num_shares = Decimal(row["No. of shares"])
        price_share = Decimal(row["Price / share"])
        exchange_rate = read_decimal(row["Exchange rate"], default=Decimal("1.0"))

        conversion_fee = row.get("Currency conversion fee")
        currency_conversion_fee = row.get("Currency (Currency conversion fee)")

        if conversion_fee and not currency_conversion_fee:
            raise ParseError(
                self._csv_file, row, "Conversion fee found but no fee currency given"
            )

        fx_fee = (
            Money(conversion_fee, currency_conversion_fee)
            if conversion_fee and currency_conversion_fee
            else get_currency(total_currency).zero
        )

        stamp_duty = read_sterling(row.get("Stamp duty (GBP)"))
        finra_fee = read_sterling(row.get("Finra fee (GBP)"))

        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        if timestamp < MIN_TIMESTAMP:
            raise OrderDateError(self._csv_file, row)

        if stamp_duty and (fx_fee or finra_fee):
            raise FeesError(self._csv_file, row)

        order_class: type[Order] = Acquisition

        # TODO: If the currency for the total is different than the
        #       currency for the fees, or if the FINRA and FX fees are
        #       defined in different currencies, parsing will fail when
        #       attempting to sum incompatible money objects.

        fees = fx_fee

        if stamp_duty:
            fees += stamp_duty

        if finra_fee:
            fees += finra_fee

        if tr_type in ("Market sell", "Limit sell"):
            order_class = Disposal
            fees *= -1

        calculated_amount = round(
            (round(price_share * num_shares, 2) / exchange_rate) + fees.amount, 2
        )

        if abs(calculated_amount - total_amount) > Decimal("0.01"):
            raise_or_warn(
                CalculatedAmountError(
                    self._csv_file, row, total_amount, calculated_amount
                )
            )

        if config.include_fx_fees:
            allowable_fees = abs(fees)
        else:
            allowable_fees = stamp_duty + finra_fee

        self._orders.append(
            order_class(
                timestamp,
                isin=ISIN(isin),
                ticker=Ticker(ticker),
                name=name,
                total=Money(total_amount, total_currency) - fees,
                quantity=num_shares,
                fees=allowable_fees,
                tr_id=tr_id,
            )
        )

        logger.debug("Parsed row %s as %s\n", dict2str(row), self._orders[-1])

    def _parse_dividend(
        self,
        row: Mapping[str, str],
        tr_type: str,
        timestamp: datetime,
        tr_id: str,
        total_amount: Decimal,
        total_currency: str,
    ):
        isin = row["ISIN"]
        ticker = row["Ticker"]
        name = row["Name"]
        currency_price_share = row["Currency (Price / share)"]
        withholding_tax = read_decimal(row["Withholding tax"])
        currency_withholding_tax = row["Currency (Withholding tax)"]
        fx_conversion_fee = row["Currency conversion fee"]

        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        if fx_conversion_fee:
            raise ParseError(self._csv_file, row, "Dividend with conversion fee")

        if currency_price_share != currency_withholding_tax:
            raise ParseError(
                self._csv_file,
                row,
                "Currency is different for share price and tax withheld",
            )

        self._dividends.append(
            Dividend(
                timestamp,
                isin=ISIN(isin),
                ticker=Ticker(ticker),
                name=name,
                total=Money(total_amount, total_currency),
                withheld=Money(withholding_tax, currency_withholding_tax),
                tr_id=tr_id,
            )
        )

        logger.debug("Parsed row %s as %s\n", dict2str(row), self._dividends[-1])

    def _parse_transfer(
        self,
        row: Mapping[str, str],
        tr_type: str,
        timestamp: datetime,
        tr_id: str,
        total_amount: Decimal,
        total_currency: str,
    ):
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        if tr_type == "Withdrawal":
            total_amount = -abs(total_amount)

        self._transfers.append(
            Transfer(timestamp, tr_id=tr_id, total=Money(total_amount, total_currency))
        )

        logger.debug("Parsed row %s as %s\n", dict2str(row), self._transfers[-1])

    def _parse_interest(
        self,
        row: Mapping[str, str],
        tr_type: str,
        timestamp: datetime,
        tr_id: str,
        total_amount: Decimal,
        total_currency: str,
    ):
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        self._interest.append(
            Interest(timestamp, tr_id=tr_id, total=Money(total_amount, total_currency))
        )

        logger.debug("Parsed row %s as %s\n", dict2str(row), self._interest[-1])
