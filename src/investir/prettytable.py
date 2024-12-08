from collections.abc import Callable
from datetime import date
from decimal import Decimal
from typing import Any

import prettytable

from investir.utils import boldify, unboldify


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
    def __init__(self, *args, **kwargs) -> None:
        kwargs["field_names"] = list(map(lambda f: boldify(f), kwargs["field_names"]))

        super().__init__(*args, **kwargs)

        for f in self.field_names:
            plain_f = unboldify(f)

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

        self.hrules = prettytable.HEADER
        self.vrules = prettytable.NONE
        self.invisible_fields: set[str] = set()

    def __bool__(self) -> bool:
        return len(self.rows) > 0

    def hide_field(self, field_name: str) -> None:
        self.invisible_fields.add(field_name)

    def to_string(self, leading_nl: bool = True) -> str:
        nl = "\n" if leading_nl else ""

        fields = [
            f for f in self.field_names if unboldify(f) not in self.invisible_fields
        ]

        return f"{nl}{self.get_string(fields=fields)}\n"
