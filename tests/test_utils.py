import datetime
from decimal import Decimal

import pytest

from investir.config import config
from investir.exceptions import InvestirError
from investir.typing import Year
from investir.utils import (
    boldify,
    date_to_tax_year,
    dict2str,
    multifilter,
    raise_or_warn,
    read_decimal,
    tax_year_full_date,
    tax_year_period,
    tax_year_short_date,
    unboldify,
)


def test_tax_year_period():
    tax_year_start, tax_year_end = tax_year_period(2023)
    assert tax_year_start == datetime.date(2023, 4, 6)
    assert tax_year_end == datetime.date(2024, 4, 5)


def test_date_to_tax_year():
    assert date_to_tax_year(datetime.date(2023, 4, 5)) == 2022
    assert date_to_tax_year(datetime.date(2023, 4, 6)) == 2023
    assert date_to_tax_year(datetime.date(2024, 4, 5)) == 2023
    assert date_to_tax_year(datetime.date(2024, 4, 6)) == 2024


def test_tax_year_short_date():
    assert tax_year_short_date(Year(2023)) == "2023/24"


def test_tax_year_full_date():
    assert tax_year_full_date(Year(2023)) == "6th April 2023 to 5th April 2024"


def test_multifilter():
    nums = [1, 2, 3, 4, 5, 6]

    nums_filtered = multifilter(None, nums)
    assert nums_filtered == nums

    nums_filtered = multifilter([], nums)
    assert nums_filtered == nums

    nums_filtered = multifilter([lambda x: x % 2 == 0, lambda x: x > 3], nums)
    assert list(nums_filtered) == [4, 6]


def test_raise_or_warn():
    config.strict = True
    with pytest.raises(InvestirError):
        raise_or_warn(InvestirError("Error"))

    config.strict = False
    raise_or_warn(InvestirError("Error"))


def test_read_decimal():
    assert read_decimal("") == Decimal("0.0")
    assert read_decimal(" ") == Decimal("0.0")
    assert read_decimal("0.0") == Decimal("0.0")
    assert read_decimal("2.5") == Decimal("2.5")
    assert read_decimal("", Decimal("2.7")) == Decimal("2.7")


def test_dict2str():
    d = {"a": "A", "b": "", "c": "C", "d": " "}
    assert dict2str(d) == "{'a': 'A', 'c': 'C'}"


def test_boldify_and_unboldify():
    bold_foo = boldify("foo")
    assert bold_foo == "\x1b[1mfoo\x1b[0m"
    assert unboldify(bold_foo) == "foo"
