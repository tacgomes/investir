from collections.abc import Callable
from decimal import Decimal
from typing import Any

import prettytable


class PrettyTable(prettytable.PrettyTable):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        def decimal_fmt(precision: int) -> Callable[[str, Any], str]:
            def _fmt(_field, val) -> str:
                if val is None:
                    return ""
                elif isinstance(val, Decimal):
                    return f"{val:.{precision}f}"
                else:
                    return f"{val}"

            return _fmt

        for f in kwargs["field_names"]:
            match f.split()[0], f.split()[-1]:
                case ("Name", _):
                    self.custom_format["Name"] = lambda _, val: f"{val:8}"
                    self.align[f] = "l"

                case ("Quantity", _):
                    self.custom_format["Quantity"] = decimal_fmt(8)
                    self.align[f] = "r"

                case (_, "(£)") | (_, "(%)"):
                    self.custom_format[f] = decimal_fmt(2)
                    self.align[f] = "r"

                case _:
                    self.align[f] = "l"

        self.vrules = prettytable.NONE
