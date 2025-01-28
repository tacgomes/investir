import math
from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import KW_ONLY, dataclass
from datetime import date
from decimal import Decimal
from enum import Enum
from functools import cache
from typing import Any, Mapping, Set

import prettytable
from moneyed import Currency, Money

from investir.const import BASE_CURRENCY
from investir.utils import boldify


class OutputFormat(str, Enum):
    TEXT = "text"
    CSV = "csv"
    JSON = "json"
    HTML = "html"


class Format(Enum):
    DATE = 1
    DECIMAL = 2
    QUANTITY = 3
    MONEY = 4


def date_format(format: str) -> Callable[[str, Any], str]:
    def _date_format(_field, val) -> str:
        if isinstance(val, date):
            return val.strftime(format)
        return val

    return _date_format


def decimal_format(precision: int) -> Callable[[str, Any], str]:
    def _decimal_format(_field, val) -> str:
        if isinstance(val, Decimal):
            return f"{val:.{precision}f}"
        elif isinstance(val, str):
            return val
        else:
            return ""

    return _decimal_format


def money_format(show_currency: bool) -> Callable[[str, Any], str]:
    def _money_format(_field, val) -> str:
        if isinstance(val, Money):
            precision = currency_precision(val.currency)
            if show_currency:
                return f"{val.amount:.{precision}f} {val.currency}"
            else:
                return f"{val.amount:.{precision}f}"
        elif isinstance(val, str):
            return val
        else:
            return ""

    return _money_format


@cache
def currency_precision(currency: Currency) -> int:
    return int(math.log10(currency.sub_unit))


@dataclass
class Field:
    name: str
    format: Format | None = None
    _: KW_ONLY
    visible: bool = True
    show_sum: bool = False


class PrettyTable(prettytable.PrettyTable):
    def __init__(
        self,
        fields: Sequence[Field],
        **kwargs,
    ) -> None:
        super().__init__([field.name for field in fields], **kwargs)

        self.hrules = prettytable.HEADER
        self.vrules = prettytable.NONE

        self.__fields = fields

    def __bool__(self) -> bool:
        return len(self.rows) > 0

    # @override
    def get_csv_string(self, **kwargs) -> str:
        import csv
        import io

        options = self._get_options(kwargs)
        csv_options = {
            key: value for key, value in kwargs.items() if key not in options
        }
        csv_buffer = io.StringIO()
        csv_writer = csv.writer(csv_buffer, **csv_options)

        if options.get("header"):
            csv_writer.writerow(self._get_expanded_field_names())

        for row in self._get_expanded_rows(options):
            csv_writer.writerow(row)

        return csv_buffer.getvalue()

    # @override
    def get_json_string(self, **kwargs) -> str:
        import json

        options = self._get_options(kwargs)
        json_options: Any = {"indent": 4, "separators": (",", ": "), "sort_keys": True}
        json_options.update(
            {key: value for key, value in kwargs.items() if key not in options}
        )
        objects: list[Any] = []

        field_names = self._get_expanded_field_names()

        if options.get("header"):
            objects.append(field_names)

        for row in self._get_expanded_rows(options):
            objects.append(dict(zip(field_names, row, strict=False)))

        return json.dumps(objects, **json_options)

    def to_string(
        self, format: OutputFormat = OutputFormat.TEXT, leading_nl: bool = True
    ) -> str:
        if format in (OutputFormat.TEXT, OutputFormat.HTML):
            self._set_fields_names(bold_text=format == OutputFormat.TEXT)

        self._set_fields_format()

        if (
            self.rows
            and any(field.show_sum for field in self.__fields)
            and format in (OutputFormat.TEXT, OutputFormat.HTML)
        ):
            self._add_total_row()

        start_nl = "\n" if leading_nl else ""
        end_nl = "\n" if format == OutputFormat.TEXT else ""

        fields = [field.name for field in self.__fields if field.visible]

        kwargs: dict[str, Any] = {"fields": fields}
        if format == OutputFormat.JSON:
            kwargs["default"] = str

        table_str = self.get_formatted_string(format, **kwargs)

        if format == OutputFormat.CSV:
            table_str = table_str.rstrip()

        return f"{start_nl}{table_str}{end_nl}"

    def _set_fields_names(self, bold_text: bool) -> None:
        for field in self.__fields:
            if field.format == Format.MONEY:
                currencies = self._get_currencies(field.name)
                if len(currencies) == 0:
                    field.name += f" ({BASE_CURRENCY})"
                elif len(currencies) == 1:
                    currency = next(iter(currencies))
                    field.name += f" ({currency.code})"

            if bold_text:
                field.name = boldify(field.name)

        self.field_names = [field.name for field in self.__fields]

    def _set_fields_format(self) -> None:
        for field in self.__fields:
            match field.format:
                case Format.DATE:
                    self.custom_format[field.name] = date_format("%d/%m/%Y")
                    self.align[field.name] = "l"
                case Format.DECIMAL:
                    self.custom_format[field.name] = decimal_format(2)
                    self.align[field.name] = "r"
                case Format.QUANTITY:
                    self.custom_format[field.name] = decimal_format(8)
                    self.align[field.name] = "r"
                case Format.MONEY:
                    self.custom_format[field.name] = money_format(
                        show_currency=self._is_multicurrency(field.name)
                    )
                    self.align[field.name] = "r"
                case _:
                    self.align[field.name] = "l"

    def _add_total_row(self) -> None:
        self.add_row(
            [
                self._sum_field(field) if field.show_sum else ""
                for field in self.__fields
            ]
        )

    def _sum_field(self, field: Field) -> str:
        idx = self._field_index(field.name)

        # TODO: Round money objects based on their subunit instead of
        #       hardcoding the number of decimals to 2.

        if field.format == Format.MONEY and self._is_multicurrency(field.name):
            totals: dict[Currency, Decimal] = defaultdict(Decimal)
            for row in self.rows:
                if row[idx]:
                    totals[row[idx].currency] += round(row[idx].amount, 2)

            return "\n".join(f"{total} {cur}" for cur, total in totals.items())

        total = sum(
            (
                round(row[idx].amount if isinstance(row[idx], Money) else row[idx], 2)
                for row in self.rows
                if row[idx] and row[idx] != "n/a"
            ),
        )

        return f"{total:.2f}"

    def _field_index(self, field_name: str) -> int:
        return next(
            idx for idx, field in enumerate(self.__fields) if field.name == field_name
        )

    def _get_currencies(self, field_name: str) -> Set[Currency]:
        idx = self._field_index(field_name)
        return set(row[idx].currency for row in self.rows if row[idx])

    def _is_multicurrency(self, field_name: str) -> bool:
        return len(self._get_currencies(field_name)) > 1

    def _get_expanded_field_names(self) -> Sequence[str]:
        field_names = []

        for field in self.__fields:
            field_names.append(field.name)
            if field.format == Format.MONEY:
                field_names.append(f"{field.name} (Currency)")

        return field_names

    def _get_expanded_rows(self, options: Mapping) -> Sequence[Sequence[Any]]:
        return [self._get_expanded_row(row) for row in self._get_rows(options)]

    def _get_expanded_row(self, row: Sequence[Any]) -> Sequence[Any]:
        out_row: list[Any] = []

        for idx, field in enumerate(row):
            if self.__fields[idx].format == Format.MONEY:
                if isinstance(field, Money):
                    out_row += [field.amount, field.currency]
                else:
                    out_row += [field, None]
            else:
                out_row.append(field)

        return out_row
