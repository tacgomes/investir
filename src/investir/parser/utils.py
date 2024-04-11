from decimal import Decimal


def read_decimal(val: str, default: Decimal = Decimal('0.0')) -> Decimal:
    return Decimal(val) if val.strip() else default
