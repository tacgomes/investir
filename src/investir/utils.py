import logging
from collections.abc import Callable, Iterable, Mapping, Sequence
from datetime import date
from decimal import Decimal
from typing import Final

from moneyed import GBP, Money

from investir.config import config
from investir.typing import TaxYear

logger = logging.getLogger(__name__)

TAX_YEAR_START_MONTH: Final = 4
TAX_YEAR_START_DAY: Final = 6


def date_to_tax_year(d: date) -> TaxYear:
    ty_start = date(d.year, TAX_YEAR_START_MONTH, TAX_YEAR_START_DAY)
    return TaxYear(d.year + 1) if d >= ty_start else TaxYear(d.year)


def tax_year_short_date(tax_year: TaxYear) -> str:
    return f"{tax_year - 1}/{(tax_year) % 100}"


def tax_year_full_date(tax_year: TaxYear) -> str:
    return f"6th April {tax_year - 1} to 5th April {tax_year}"


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


def read_sterling(amount: str | None) -> Money | None:
    return (
        Money(amount=amount, currency="GBP")
        if amount is not None and amount.strip()
        else None
    )


def sterling(amount: str) -> Money:
    return Money(amount=amount, currency=GBP)


def dict2str(d: Mapping[str, str]) -> str:
    return str({k: v for k, v in d.items() if v.strip()})


def boldify(text: str) -> str:
    return f"\033[1m{text}\033[0m"
