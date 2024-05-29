from decimal import Decimal

from investir.parser.utils import read_decimal, dict2str


def test_read_decimal():
    assert read_decimal("") == Decimal("0.0")
    assert read_decimal(" ") == Decimal("0.0")
    assert read_decimal("0.0") == Decimal("0.0")
    assert read_decimal("2.5") == Decimal("2.5")
    assert read_decimal("", Decimal("2.7")) == Decimal("2.7")


def test_dict2str():
    d = {"a": "A", "b": "", "c": "C", "d": " "}
    assert dict2str(d) == "{'a': 'A', 'c': 'C'}"
