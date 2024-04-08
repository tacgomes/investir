import datetime

from collections.abc import Iterable


TAX_YEAR_MONTH = 4
TAX_YEAR_START_DAY = 6
TAX_YEAR_END_DAY = 5


def tax_year_period(tax_year: int) -> tuple[datetime.date, datetime.date]:
    tax_year_start = datetime.date(
        tax_year, TAX_YEAR_MONTH, TAX_YEAR_START_DAY)
    tax_year_end = datetime.date(
        tax_year + 1, TAX_YEAR_MONTH, TAX_YEAR_END_DAY)
    return tax_year_start, tax_year_end


def date_to_tax_year(date: datetime.date) -> int:
    tax_year_start, _ = tax_year_period(date.year)
    if date >= tax_year_start:
        return tax_year_start.year
    return tax_year_start.year - 1


def multiple_filter(filters, iterable: Iterable):
    if not filters:
        return iterable
    return filter(lambda x: all(f(x) for f in filters), iterable)
