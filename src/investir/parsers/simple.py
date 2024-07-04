import csv
import logging

from decimal import Decimal
from pathlib import Path
from typing import Final

from dateutil.parser import parse as parse_timestamp

from investir.const import MIN_TIMESTAMP
from investir.utils import read_decimal, dict2str
from investir.exceptions import (
    OrderDateError,
    TransactionTypeError,
)
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


logger = logging.getLogger(__name__)


class SimpleParser(Parser):
    FIELDS: Final = (
        "Action",
        "Timestamp",
        "Amount",
        "Ticker",
        "Quantity",
        "Fees",
        "Notes",
    )

    def __init__(self, csv_file: Path) -> None:
        self._csv_file = csv_file
        self._orders: list[Order] = []
        self._dividends: list[Dividend] = []
        self._transfers: list[Transfer] = []
        self._interest: list[Interest] = []

    @staticmethod
    def name() -> str:
        return "Simple"

    def can_parse(self) -> bool:
        with self._csv_file.open(encoding="utf-8") as file:
            reader = csv.DictReader(file)
            if reader.fieldnames:
                return tuple(reader.fieldnames) == self.FIELDS

        return False

    def parse(self) -> ParsingResult:
        with self._csv_file.open(encoding="utf-8") as file:
            for row in csv.DictReader(file):
                self._parse_row(row)

        return ParsingResult(
            self._orders, self._dividends, self._transfers, self._interest
        )

    def _parse_row(self, row: dict[str, str]) -> None:
        action = row["Action"]
        timestamp = parse_timestamp(row["Timestamp"])
        ticker = row["Ticker"]
        quantity = read_decimal(row["Quantity"])
        amount = Decimal(row["Amount"])
        fees = read_decimal(row["Fees"])
        notes = row["Notes"]

        match action:
            case "Acquisition" | "Disposal":
                if timestamp < MIN_TIMESTAMP:
                    raise OrderDateError(self._csv_file, row)

                order_class: type[Order] = Acquisition

                if action == "Disposal":
                    order_class = Disposal
                    fees *= -1

                self._orders.append(
                    order_class(
                        timestamp,
                        amount=amount - fees,
                        ticker=Ticker(ticker),
                        quantity=quantity,
                        fees=abs(fees),
                        notes=notes,
                    )
                )

                logging.debug("Parsed row %s as %s\n", dict2str(row), self._orders[-1])

            case "Dividend":
                self._dividends.append(
                    Dividend(
                        timestamp,
                        amount=amount,
                        ticker=Ticker(ticker),
                        withheld=None,
                        notes=notes,
                    )
                )
                logging.debug(
                    "Parsed row %s as %s\n", dict2str(row), self._dividends[-1]
                )

            case "Interest":
                self._interest.append(
                    Interest(
                        timestamp,
                        amount=amount,
                        notes=notes,
                    )
                )
                logging.debug(
                    "Parsed row %s as %s\n", dict2str(row), self._interest[-1]
                )

            case "Deposit" | "Withdrawal":
                if action == "Withdrawal":
                    amount *= -1

                self._transfers.append(
                    Transfer(
                        timestamp,
                        amount=amount,
                        notes=notes,
                    )
                )
                logging.debug(
                    "Parsed row %s as %s\n", dict2str(row), self._transfers[-1]
                )

            case _:
                raise TransactionTypeError(self._csv_file, row, action)
