import datetime
import logging

from collections.abc import Iterable
from typing import Final

from .config import config
from .typing import Year

TAX_YEAR_MONTH: Final = 4
TAX_YEAR_START_DAY: Final = 6
TAX_YEAR_END_DAY: Final = 5


def tax_year_period(tax_year: Year) -> tuple[datetime.date, datetime.date]:
    tax_year_start = datetime.date(tax_year, TAX_YEAR_MONTH, TAX_YEAR_START_DAY)
    tax_year_end = datetime.date(tax_year + 1, TAX_YEAR_MONTH, TAX_YEAR_END_DAY)
    return tax_year_start, tax_year_end


def date_to_tax_year(date: datetime.date) -> Year:
    tax_year_start, _ = tax_year_period(Year(date.year))
    if date >= tax_year_start:
        return Year(tax_year_start.year)
    return Year(tax_year_start.year - 1)


def multiple_filter(filters, iterable: Iterable):
    if not filters:
        return iterable
    return filter(lambda x: all(f(x) for f in filters), iterable)


def raise_or_warn(ex: Exception):
    if config.strict:
        raise ex
    logging.warning(ex)
