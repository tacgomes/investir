import datetime
import logging
from collections.abc import Callable, Iterable, Mapping, Sequence
from decimal import Decimal
from typing import Final

from prettytable import PrettyTable

from investir.config import config
from investir.typing import Year

logger = logging.getLogger(__name__)

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


def multifilter(filters: Sequence[Callable] | None, iterable: Iterable) -> Iterable:
    if not filters:
        return iterable
    return filter(lambda x: all(f(x) for f in filters), iterable)


def raise_or_warn(ex: Exception) -> None:
    if config.strict:
        raise ex
    logger.warning(ex)


def read_decimal(val: str, default: Decimal = Decimal("0.0")) -> Decimal:
    return Decimal(val) if val.strip() else default


def dict2str(d: Mapping[str, str]) -> str:
    return str({k: v for k, v in d.items() if v.strip()})


def printtable(
    table: PrettyTable, leading_newline: bool = True, trailing_newline: bool = True
) -> None:
    preamble = epilog = ""

    if leading_newline and config.log_level != logging.CRITICAL:
        preamble = "\n"

    if trailing_newline:
        epilog = "\n"

    print(preamble, table, epilog, sep="")
