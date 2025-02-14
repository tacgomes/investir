import operator
from dataclasses import dataclass
from decimal import Decimal
from functools import reduce
from typing import no_type_check

from moneyed import Currency, Money

from investir.const import BASE_CURRENCY


@no_type_check
def add(a: Money | None, b: Money | None) -> Money | None:
    match a, b:
        case None, None:
            return None
        case _, None:
            return a
        case None, _:
            return b
        case _, _:
            return a + b


@no_type_check
def sub(a: Money | None, b: Money | None) -> Money | None:
    match a, b:
        case None, None:
            return None
        case _, None:
            return a
        case None, _:
            return -b
        case _, _:
            return a - b


def mul(m: Money | None, v: Decimal) -> Money | None:
    return m * v if m is not None else None


def div(m: Money | None, v: Decimal) -> Money | None:
    return m / v if m is not None else None  # type: ignore[return-value]


@dataclass(frozen=True)
class Fees:
    """Holds fees incurred on a share acquisition/disposal order"""

    """Stamp Duty or Stamp Duty Reserve Tax fee"""
    stamp_duty: Money | None = None

    """Currency conversion fee"""
    forex: Money | None = None

    """Financial Industry Regulatory Authority fee"""
    finra: Money | None = None

    """Securities and Exchange Commission fee"""
    sec: Money | None = None

    default_currency: Currency = BASE_CURRENCY

    @property
    def total(self) -> Money:
        fees_set = [
            fee for fee in [self.stamp_duty, self.forex, self.finra, self.sec] if fee
        ]

        if fees_set and (total := reduce(operator.add, fees_set)):
            return total

        return self.default_currency.zero

    def __add__(self: "Fees", other: "Fees") -> "Fees":
        return Fees(
            stamp_duty=add(self.stamp_duty, other.stamp_duty),
            forex=add(self.forex, other.forex),
            finra=add(self.finra, other.finra),
            sec=add(self.sec, other.sec),
            default_currency=self.default_currency,
        )
        return Fees.apply_operator(self, other, operator.add)

    def __sub__(self: "Fees", other: "Fees") -> "Fees":
        return Fees(
            stamp_duty=sub(self.stamp_duty, other.stamp_duty),
            forex=sub(self.forex, other.forex),
            finra=sub(self.finra, other.finra),
            sec=sub(self.sec, other.sec),
            default_currency=self.default_currency,
        )
        return Fees.apply_operator(self, other, operator.add)

    def __mul__(self: "Fees", val: Decimal) -> "Fees":
        return Fees(
            stamp_duty=mul(self.stamp_duty, val),
            forex=mul(self.forex, val),
            finra=mul(self.finra, val),
            sec=mul(self.sec, val),
            default_currency=self.default_currency,
        )

    @no_type_check
    def __truediv__(self: "Fees", val: Decimal) -> "Fees":
        return Fees(
            stamp_duty=div(self.stamp_duty, val),
            forex=div(self.forex, val),
            finra=div(self.finra, val),
            sec=div(self.sec, val),
            default_currency=self.default_currency,
        )
