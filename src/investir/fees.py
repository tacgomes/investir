import operator
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from functools import partial, reduce
from typing import no_type_check

from moneyed import Currency, Money

from investir.const import BASE_CURRENCY

ArithmeticFn = Callable[[Money | None, Money | None], Money | None]
ScalarFn = Callable[[Money | None], Money | None]


def arithmetic_op(fn: ArithmeticFn, a: "Fees", b: "Fees") -> "Fees":
    return Fees(
        stamp_duty=fn(a.stamp_duty, b.stamp_duty),
        forex=fn(a.forex, b.forex),
        finra=fn(a.finra, b.finra),
        sec=fn(a.sec, b.sec),
        default_currency=a.default_currency,
    )


def scalar_op(fn: ScalarFn, fees: "Fees") -> "Fees":
    return Fees(
        stamp_duty=fn(fees.stamp_duty),
        forex=fn(fees.forex),
        finra=fn(fees.finra),
        sec=fn(fees.sec),
        default_currency=fees.default_currency,
    )


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
        return arithmetic_op(add, self, other)

    def __sub__(self: "Fees", other: "Fees") -> "Fees":
        return arithmetic_op(sub, self, other)

    def __mul__(self: "Fees", val: Decimal) -> "Fees":
        return scalar_op(partial(mul, v=val), self)

    @no_type_check
    def __truediv__(self: "Fees", val: Decimal) -> "Fees":
        return scalar_op(partial(div, v=val), self)
