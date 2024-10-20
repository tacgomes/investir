from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path

from investir.typing import ISIN, Ticker


class InvestirError(Exception):
    pass


class ParseError(InvestirError):
    def __init__(self, file: Path, row: Mapping[str, str], message: str) -> None:
        super().__init__(f"{file}: {message} on row {row}")


class TransactionTypeError(ParseError):
    def __init__(self, file: Path, row: Mapping[str, str], tr_type: str) -> None:
        super().__init__(file, row, f"Invalid type of transaction '({tr_type})'")


class CurrencyError(ParseError):
    def __init__(self, file: Path, row: Mapping[str, str], currency: str) -> None:
        super().__init__(file, row, f"Currency not supported ('{currency}')")


class CalculatedAmountError(ParseError):
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
            f"Calculated amount (£{cal_amount}) is different than the "
            f"expected value (£{csv_amount})",
        )


class FeesError(ParseError):
    def __init__(self, file: Path, row: Mapping[str, str]) -> None:
        super().__init__(file, row, "Stamp duty and conversion fees are both non-zero")


class OrderDateError(ParseError):
    def __init__(self, file: Path, row: Mapping[str, str]) -> None:
        super().__init__(
            file, row, "Orders executed before 6 April of 2008 are not supported"
        )


class IncompleteRecordsError(InvestirError):
    def __init__(self, isin: ISIN, name: str) -> None:
        super().__init__(
            f"Records appear to be incomplete for {name} ({isin}): "
            f"share quantity cannot be negative"
        )


class AmbiguousTickerError(InvestirError):
    def __init__(self, ticker: Ticker) -> None:
        super().__init__(f"Ticker {ticker} is ambiguous (used on different securities)")
