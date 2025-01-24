from collections.abc import Callable, Sequence
from dataclasses import KW_ONLY, dataclass
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Any

import prettytable

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

    def to_string(self, format: OutputFormat, leading_nl: bool = True) -> str:
        if format == OutputFormat.TEXT:
            for field in self.__fields:
                field.name = boldify(field.name)
            self.field_names = [field.name for field in self.__fields]

        if (
            self.rows
            and any(field.show_sum for field in self.__fields)
            and format in (OutputFormat.TEXT, OutputFormat.HTML)
        ):
            self._insert_totals_row()

        self._apply_formatting()

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

    def _insert_totals_row(self) -> None:
        totals_row = []

        for idx, field in enumerate(self.__fields):
            if field.show_sum:
                total = sum(
                    (
                        round(row[idx], 2)
                        for row in self.rows
                        if row[idx] and row[idx] != "n/a"
                    ),
                    Decimal("0.0"),
                )
                totals_row.append(total)
            else:
                totals_row.append("")

        self.add_row(totals_row)

    def _apply_formatting(self) -> None:
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
                case _:
                    self.align[field.name] = "l"
