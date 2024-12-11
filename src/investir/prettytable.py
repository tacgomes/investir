from collections.abc import Callable, Sequence, Set
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Any

import prettytable

from investir.utils import boldify, unboldify


class OutputFormat(str, Enum):
    TEXT = "text"
    CSV = "csv"
    JSON = "json"
    HTML = "html"


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


class PrettyTable(prettytable.PrettyTable):
    def __init__(
        self,
        field_names: Sequence[str],
        hidden_fields: Sequence[str] | None = None,
        show_total_fields: Sequence[str] | None = None,
        **kwargs,
    ) -> None:
        super().__init__(field_names, **kwargs)

        self.hrules = prettytable.HEADER
        self.vrules = prettytable.NONE
        self._hidden_fields: Set[str] = frozenset(hidden_fields or [])
        self._show_total_fields: Set[str] = frozenset(show_total_fields or [])

    def __bool__(self) -> bool:
        return len(self.rows) > 0

    def to_string(self, format: OutputFormat, leading_nl: bool = True) -> str:
        if (
            self.rows
            and self._show_total_fields
            and format in (OutputFormat.TEXT, OutputFormat.HTML)
        ):
            self._insert_totals_row()

        self._apply_formatting(bold_titles=format == OutputFormat.TEXT)

        start_nl = "\n" if leading_nl else ""
        end_nl = "\n" if format == OutputFormat.TEXT else ""

        fields = [
            f for f in self.field_names if unboldify(f) not in self._hidden_fields
        ]

        kwargs: dict[str, Any] = {"fields": fields}
        if format == OutputFormat.JSON:
            kwargs["default"] = str

        table_str = self.get_formatted_string(format, **kwargs)

        if format == OutputFormat.CSV:
            table_str = table_str.rstrip()

        return f"{start_nl}{table_str}{end_nl}"

    def _insert_totals_row(self) -> None:
        totals_row = []

        for i, f in enumerate(self.field_names):
            if unboldify(f) in self._show_total_fields:
                total = sum(
                    (
                        round(row[i], 2)
                        for row in self.rows
                        if row[i] and row[i] != "n/a"
                    ),
                    Decimal("0.0"),
                )
                totals_row.append(total)
            else:
                totals_row.append("")

        self.add_row(totals_row)

    def _apply_formatting(self, bold_titles: bool) -> None:
        if bold_titles:
            self.field_names = list(map(lambda f: boldify(f), self.field_names))

        for f in self.field_names:
            plain_f = unboldify(f) if bold_titles else f

            match plain_f.split()[0].strip(), plain_f.split()[-1]:
                case ("Date", _) | (_, "Date"):
                    self.custom_format[f] = date_format("%d/%m/%Y")
                    self.align[f] = "l"
                case ("Quantity", _):
                    self.custom_format[f] = decimal_format(8)
                    self.align[f] = "r"

                case (_, "(£)") | (_, "(%)"):
                    self.custom_format[f] = decimal_format(2)
                    self.align[f] = "r"

                case _:
                    self.align[f] = "l"
