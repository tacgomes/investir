from decimal import Decimal


class ParserError(Exception):

    def __init__(self, file: str, message: str) -> None:
        super().__init__(f"{message}, while parsing {file}")


class CalculatedAmountError(Exception):

    def __init__(self, file: str, cal_amount: Decimal, csv_amount: Decimal) -> None:
        super().__init__(
            f"Calculated amount (£{cal_amount}) differs from the total "
            f"amount read` (£{csv_amount}), while parsing {file}"
        )


class FeeError(Exception):

    def __init__(self, file: str) -> None:
        super().__init__(
            f"Both stamp duty and forex fee fields are non-zero"
            f", while parsing {file}"
        )
