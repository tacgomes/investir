from decimal import Decimal


def read_decimal(val: str) -> Decimal:
    return Decimal(val) if val.strip() else Decimal('0.0')
