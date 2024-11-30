from collections.abc import Callable
from decimal import Decimal
from typing import Any

import prettytable


def decimal_format(precision: int) -> Callable[[str, Any], str]:
    def _decimal_format(_field, val) -> str:
        if val is None:
            return ""
        elif isinstance(val, Decimal):
            return f"{val:.{precision}f}"
        else:
            return f"{val}"

    return _decimal_format


class PrettyTable(prettytable.PrettyTable):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        for f in kwargs["field_names"]:
            match f.split()[0], f.split()[-1]:
                case ("Name", _):
                    self.custom_format["Name"] = lambda _, val: f"{val:8}"
                    self.align[f] = "l"

                case ("Quantity", _):
                    self.custom_format["Quantity"] = decimal_format(8)
                    self.align[f] = "r"

                case (_, "(£)") | (_, "(%)"):
                    self.custom_format[f] = decimal_format(2)
                    self.align[f] = "r"

                case _:
                    self.align[f] = "l"

        self.vrules = prettytable.NONE

    def to_string(self, leading_nl: bool = True) -> str:
        nl = "\n" if leading_nl else ""
        return f"{nl}{self.get_string()}\n"

    def __bool__(self) -> bool:
        return len(self.rows) > 0
