import datetime

from investir.utils import tax_year_period, date_to_tax_year


def test_tax_year_period():
    tax_year_start, tax_year_end = tax_year_period(2023)
    assert tax_year_start == datetime.date(2023, 4, 6)
    assert tax_year_end == datetime.date(2024, 4, 5)


def test_date_to_tax_year():
    assert date_to_tax_year(datetime.date(2023, 4, 5)) == 2022
    assert date_to_tax_year(datetime.date(2023, 4, 6)) == 2023
    assert date_to_tax_year(datetime.date(2024, 4, 5)) == 2023
    assert date_to_tax_year(datetime.date(2024, 4, 6)) == 2024
