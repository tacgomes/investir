from collections.abc import Mapping, Sequence
from decimal import Decimal
from pathlib import Path

from investir.typing import ISIN, Ticker


class InvestirError(Exception):
    skippable = False


class FieldUnknownError(InvestirError):
    skippable = True

    def __init__(self, fields: Sequence[str]) -> None:
        super().__init__(f"Unknown fields found: {', '.join(fields)}'")


class ParseError(InvestirError):
    def __init__(self, file: Path, row: Mapping[str, str], message: str) -> None:
        super().__init__(f"{file}: {message} on row {row}")


class TransactionTypeError(ParseError):
    skippable = True

    def __init__(self, file: Path, row: Mapping[str, str], tr_type: str) -> None:
        super().__init__(file, row, f"Invalid type of transaction '({tr_type})'")


class CalculatedAmountError(ParseError):
    skippable = True

    def __init__(
        self,
        file: Path,
        row: Mapping[str, str],
        csv_amount: Decimal,
        cal_amount: Decimal,
    ) -> None:
        super().__init__(
            file,
            row,
            f"Calculated amount ({cal_amount}) is different than the "
            f"expected value ({csv_amount})",
        )


class FeesError(ParseError):
    def __init__(self, file: Path, row: Mapping[str, str], fee_a: str, fee_b) -> None:
        super().__init__(
            file,
            row,
            f"Incompatible fees have a non-zero amount: '{fee_a}' and '{fee_b}'",
        )


class OrderDateError(ParseError):
    def __init__(self, file: Path, row: Mapping[str, str]) -> None:
        super().__init__(
            file, row, "Orders executed before 6 April of 2008 are not supported"
        )


class IncompleteRecordsError(InvestirError):
    skippable = True

    def __init__(self, isin: ISIN, name: str) -> None:
        super().__init__(
            f"Records appear to be incomplete for {name} ({isin}): "
            f"share quantity cannot be negative"
        )


class AmbiguousTickerError(InvestirError):
    def __init__(self, ticker: Ticker) -> None:
        super().__init__(f"Ticker {ticker} is ambiguous (used on different securities)")
