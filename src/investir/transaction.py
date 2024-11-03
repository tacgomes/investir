import operator
import sys
from abc import ABC
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from datetime import date, datetime
from decimal import Decimal
from functools import reduce
from typing import ClassVar, TypeVar

from investir.findata.types import Split
from investir.typing import ISIN, Ticker, Year
from investir.utils import date_to_tax_year

if sys.version_info >= (3, 11):
    from typing import Self
else:
    Self = TypeVar("Self", bound="Order")


@dataclass(frozen=True)
class Transaction(ABC):
    timestamp: datetime
    amount: Decimal
    tr_id: str | None = None
    notes: str | None = None

    @property
    def date(self) -> date:
        return self.timestamp.date()

    def tax_year(self) -> Year:
        return date_to_tax_year(self.date)


@dataclass(kw_only=True, frozen=True)
class Order(Transaction, ABC):
    number: int = field(default=0, compare=False)
    isin: ISIN
    ticker: Ticker | None = None
    name: str = ""
    quantity: Decimal
    original_quantity: Decimal | None = None
    fees: Decimal = Decimal("0.0")

    order_count: ClassVar[int] = 0

    def __post_init__(self) -> None:
        Order.order_count += 1
        object.__setattr__(self, "number", Order.order_count)

    @property
    def price(self) -> Decimal:
        return self.amount / self.quantity

    def split(self: Self, split_quantity: Decimal) -> tuple[Self, Self]:
        assert self.quantity >= split_quantity

        match_amount = self.price * split_quantity
        match_quantity = split_quantity
        match_fees = self.fees / self.quantity * split_quantity

        remainder_amount = self.amount - match_amount
        remainder_quantity = self.quantity - match_quantity
        remainder_fees = self.fees - match_fees

        match = replace(
            self,
            amount=match_amount,
            quantity=match_quantity,
            fees=match_fees,
            notes=f"Splitted from order {self.number}",
        )

        remainder = replace(
            self,
            amount=remainder_amount,
            quantity=remainder_quantity,
            fees=remainder_fees,
            notes=f"Splitted from order {self.number}",
        )

        return match, remainder

    @staticmethod
    def merge(*orders: "Order") -> "Order":
        assert len(orders) > 1

        isin = orders[0].isin
        assert all(order.isin == isin for order in orders)

        timestamp = orders[0].timestamp.replace(
            hour=0, minute=0, second=0, microsecond=0
        )

        amount = Decimal(sum(order.amount for order in orders))
        quantity = Decimal(sum(order.quantity for order in orders))
        fees = Decimal(sum(order.fees for order in orders))

        notes = "Merged from orders "
        notes += ",".join(str(order.number) for order in orders)

        return replace(
            orders[0],
            timestamp=timestamp,
            amount=amount,
            quantity=quantity,
            fees=fees,
            notes=notes,
        )

    def adjust_quantity(self, splits: Sequence[Split]) -> "Order":
        split_ratios = [s.ratio for s in splits if self.timestamp < s.date_effective]

        if not split_ratios:
            return self

        quantity = reduce(operator.mul, [self.quantity, *split_ratios])

        return replace(
            self,
            isin=self.isin,
            quantity=quantity,
            original_quantity=self.quantity,
            notes=(
                f"Adjusted from order {self.number} after applying the "
                f"following split ratios: {', '.join(map(str, split_ratios))}"
            ),
        )


@dataclass(frozen=True)
class Acquisition(Order):
    @property
    def total_cost(self) -> Decimal:
        return self.amount + self.fees


@dataclass(frozen=True)
class Disposal(Order):
    @property
    def net_proceeds(self) -> Decimal:
        return self.amount - self.fees


@dataclass(kw_only=True, frozen=True)
class Dividend(Transaction):
    isin: ISIN
    name: str = ""
    ticker: Ticker | None = None
    withheld: Decimal | None


@dataclass(frozen=True)
class Transfer(Transaction):
    pass


@dataclass(frozen=True)
class Interest(Transaction):
    pass
