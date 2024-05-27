from decimal import Decimal


class InvestirError(Exception):
    pass


class ParserError(InvestirError):

    def __init__(self, file: str, message: str) -> None:
        super().__init__(f"{message}, while parsing {file}")


class CalculatedAmountError(InvestirError):

    def __init__(self, file: str, cal_amount: Decimal, csv_amount: Decimal) -> None:
        super().__init__(
            f"Calculated amount (£{cal_amount}) differs from the total "
            f"amount read` (£{csv_amount}), while parsing {file}"
        )


class FeeError(InvestirError):

    def __init__(self, file: str) -> None:
        super().__init__(
            f"Both stamp duty and forex fee fields are non-zero"
            f", while parsing {file}"
        )


class OrderTooError(InvestirError):

    def __init__(self, order: dict) -> None:
        super().__init__(f"Order made before 6 April of 2008: {order}")