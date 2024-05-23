from decimal import Decimal

from investir.parser.utils import read_decimal


def test_read_decimal():
    assert read_decimal("") == Decimal("0.0")
    assert read_decimal(" ") == Decimal("0.0")
    assert read_decimal("0.0") == Decimal("0.0")
    assert read_decimal("2.5") == Decimal("2.5")
    assert read_decimal("", Decimal("2.7")) == Decimal("2.7")
