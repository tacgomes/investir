import datetime

from investir.utils import tax_year_period, date_to_tax_year, multiple_filter


def test_tax_year_period():
    tax_year_start, tax_year_end = tax_year_period(2023)
    assert tax_year_start == datetime.date(2023, 4, 6)
    assert tax_year_end == datetime.date(2024, 4, 5)


def test_date_to_tax_year():
    assert date_to_tax_year(datetime.date(2023, 4, 5)) == 2022
    assert date_to_tax_year(datetime.date(2023, 4, 6)) == 2023
    assert date_to_tax_year(datetime.date(2024, 4, 5)) == 2023
    assert date_to_tax_year(datetime.date(2024, 4, 6)) == 2024


def test_multiple_filter():
    nums = [1, 2, 3, 4, 5, 6]

    nums_filtered = multiple_filter(None, nums)
    assert nums_filtered == nums

    nums_filtered = multiple_filter([], nums)
    assert nums_filtered == nums

    nums_filtered = multiple_filter([lambda x: x % 2 == 0, lambda x: x > 3], nums)
    assert list(nums_filtered) == [4, 6]
