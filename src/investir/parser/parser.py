import logging
from collections.abc import Iterator, Mapping, Sequence
from csv import DictReader
from pathlib import Path
from typing import NamedTuple, Protocol

from investir.exceptions import FieldUnknownError
from investir.transaction import Dividend, Interest, Order, Transfer
from investir.utils import raise_or_warn

logger = logging.getLogger(__name__)


class Field:
    def __init__(self, *aliases: str, required: bool = False) -> None:
        self.aliases = list(aliases)
        self.required = required

    def __contains__(self, key: str) -> bool:
        return key in self.aliases


class Row:
    def __init__(
        self, data: Mapping[str, str], field_mapping: Mapping[str, Field]
    ) -> None:
        self.data = data
        self.field_mapping = field_mapping

    def __getitem__(self, field: str) -> str:
        if f := self.field_mapping.get(field):
            aliases = f.aliases
        else:
            aliases = [field]

        for alias in aliases:
            try:
                return self.data[alias]
            except KeyError:
                pass

        raise KeyError

    def __str__(self) -> str:
        return str({k: v for k, v in self.data.items() if v.strip()})


class ParsingResult(NamedTuple):
    orders: list[Order]
    dividends: list[Dividend]
    transfers: list[Transfer]
    interest: list[Interest]


class Parser(Protocol):
    def __init__(self, csv_file: Path) -> None:
        pass

    def can_parse(self) -> bool:
        pass

    def parse(self) -> ParsingResult:
        pass


class ParserBase:
    def __init__(self, csv_file: Path, schema: Sequence[Field]) -> None:
        self._csv_file = csv_file
        self._schema = schema
        self._orders: list[Order] = []
        self._dividends: list[Dividend] = []
        self._transfers: list[Transfer] = []
        self._interest: list[Interest] = []

    def rows(self, reverse: bool = False) -> Iterator[Row]:
        with self._csv_file.open(encoding="utf-8") as file:
            rows = DictReader(file)

            if reverse:
                rows = reversed(list(rows))  # type: ignore

            field_mapping = self._get_field_mapping()

            for row in rows:
                yield Row(row, field_mapping)

    @property
    def field_names(self) -> Sequence[str]:
        with self._csv_file.open(encoding="utf-8") as file:
            reader = DictReader(file)
            return reader.fieldnames or []

    def can_parse(self) -> bool:
        return all(
            set(f.aliases) & set(self.field_names) for f in self._schema if f.required
        )

    def add_order(self, order: Order, row: Row) -> None:
        self._orders.append(order)
        logger.debug("Parsed row %s as %s\n", row, order)

    def add_dividend(self, dividend: Dividend, row: Row) -> None:
        self._dividends.append(dividend)
        logger.debug("Parsed row %s as %s\n", row, dividend)

    def add_transfer(self, transfer: Transfer, row: Row) -> None:
        self._transfers.append(transfer)
        logger.debug("Parsed row %s as %s\n", row, transfer)

    def add_interest(self, interest: Interest, row: Row) -> None:
        self._interest.append(interest)
        logger.debug("Parsed row %s as %s\n", row, interest)

    def parsing_result(self) -> ParsingResult:
        return ParsingResult(
            self._orders, self._dividends, self._transfers, self._interest
        )

    def validate_fields(self) -> None:
        unknown_fields = [
            f for f in self.field_names if not self._is_field_in_schema(f)
        ]
        if unknown_fields:
            raise_or_warn(FieldUnknownError(unknown_fields))

    def _get_field_mapping(self) -> Mapping[str, Field]:
        field_mapping = {}
        for f in self._schema:
            if len(f.aliases) >= 2:
                for alias in f.aliases:
                    field_mapping[alias] = f
        return field_mapping

    def _is_field_in_schema(self, field_name: str) -> bool:
        return any([f for f in self._schema if field_name in f])
