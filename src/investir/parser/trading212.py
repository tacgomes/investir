import csv
import logging
from collections.abc import Mapping
from datetime import timezone
from decimal import Decimal
from pathlib import Path
from typing import Final

from dateutil.parser import parse as parse_timestamp

from investir.config import config
from investir.const import MIN_TIMESTAMP
from investir.exceptions import (
    CalculatedAmountError,
    CurrencyError,
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
from investir.utils import dict2str, raise_or_warn, read_decimal

logger = logging.getLogger(__name__)


@ParserFactory.register("Trading212")
class Trading212Parser:
    INITIAL_FIELDS: Final = (
        "Action",
        "Time",
        "ISIN",
        "Ticker",
        "Name",
        "No. of shares",
        "Price / share",
        "Currency (Price / share)",
        "Exchange rate",
    )

    MANDATORY_FIELDS: Final = (
        "Currency (Result)",
        "Total",
        "Currency (Total)",
        "Notes",
        "ID",
        "Currency conversion fee",
        "Currency (Currency conversion fee)",
    )

    OPTIONAL_FIELDS: Final = (
        "Result",
        "Withholding tax",
        "Currency (Withholding tax)",
        "Currency conversion from amount",
        "Currency (Currency conversion from amount)",
        "Currency conversion to amount",
        "Currency (Currency conversion to amount)",
        "Finra fee (GBP)",
        "Stamp duty (GBP)",
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
            "Currency conversion": lambda _: None,
        }

        with self._csv_file.open(encoding="utf-8") as file:
            for row in csv.DictReader(file):
                tr_type = row["Action"]
                if fn := parse_fn.get(tr_type):
                    currency_total = row["Currency (Total)"]
                    if currency_total != "GBP":
                        raise_or_warn(
                            CurrencyError(self._csv_file, row, currency_total)
                        )
                    fn(row)
                else:
                    raise_or_warn(TransactionTypeError(self._csv_file, row, tr_type))

        return ParsingResult(
            self._orders, self._dividends, self._transfers, self._interest
        )

    def _parse_order(self, row: Mapping[str, str]) -> None:
        action = row["Action"]
        timestamp = parse_timestamp(row["Time"])
        isin = row["ISIN"]
        ticker = row["Ticker"]
        name = row["Name"]
        num_shares = Decimal(row["No. of shares"])
        price_share = Decimal(row["Price / share"])
        exchange_rate = Decimal(row["Exchange rate"])
        total = Decimal(row["Total"])
        tr_id = row["ID"]
        fx_conversion_fee = read_decimal(row["Currency conversion fee"])
        currency_fx_conversion_fee = row["Currency (Currency conversion fee)"]
        stamp_duty = read_decimal(row.get("Stamp duty (GBP)", ""))
        finra_fee = read_decimal(row.get("Finra fee (GBP)", ""))

        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        if timestamp < MIN_TIMESTAMP:
            raise OrderDateError(self._csv_file, row)

        if stamp_duty and (fx_conversion_fee or finra_fee):
            raise FeesError(self._csv_file, row)

        if fx_conversion_fee and currency_fx_conversion_fee != "GBP":
            raise CurrencyError(self._csv_file, row, currency_fx_conversion_fee)

        order_class: type[Order] = Acquisition
        fees = stamp_duty + finra_fee + fx_conversion_fee

        if action in ("Market sell", "Limit sell"):
            order_class = Disposal
            fees *= -1

        calculated_amount = round(
            (round(price_share * num_shares, 2) / exchange_rate) + fees, 2
        )

        if abs(calculated_amount - total) > Decimal("0.01"):
            raise_or_warn(
                CalculatedAmountError(self._csv_file, row, total, calculated_amount)
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
                amount=total - fees,
                quantity=num_shares,
                fees=allowable_fees,
                tr_id=tr_id,
            )
        )

        logger.debug("Parsed row %s as %s\n", dict2str(row), self._orders[-1])

    def _parse_dividend(self, row: Mapping[str, str]):
        timestamp = parse_timestamp(row["Time"])
        isin = row["ISIN"]
        ticker = row["Ticker"]
        name = row["Name"]
        currency_price_share = row["Currency (Price / share)"]
        total = Decimal(row["Total"])
        currency_withholding_tax = row["Currency (Withholding tax)"]
        tr_id = row["ID"]
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
                amount=total,
                withheld=None,
                tr_id=tr_id,
            )
        )

        logger.debug("Parsed row %s as %s\n", dict2str(row), self._dividends[-1])

    def _parse_transfer(self, row: Mapping[str, str]):
        action = row["Action"]
        timestamp = parse_timestamp(row["Time"])
        total = Decimal(row["Total"])
        tr_id = row["ID"]

        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        if action == "Withdrawal":
            total *= -1

        self._transfers.append(Transfer(timestamp, tr_id=tr_id, amount=total))

        logger.debug("Parsed row %s as %s\n", dict2str(row), self._transfers[-1])

    def _parse_interest(self, row: Mapping[str, str]):
        timestamp = parse_timestamp(row["Time"])
        total = Decimal(row["Total"])
        tr_id = row["ID"]

        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        self._interest.append(Interest(timestamp, tr_id=tr_id, amount=total))

        logger.debug("Parsed row %s as %s\n", dict2str(row), self._interest[-1])
