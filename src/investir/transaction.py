from abc import ABC
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import ClassVar

from .utils import date_to_tax_year


@dataclass
class Transaction(ABC):
    timestamp: datetime
    amount: Decimal

    def tax_year(self) -> int:
        return date_to_tax_year(self.timestamp.date())


@dataclass(kw_only=True)
class Order(Transaction, ABC):
    id: int = 0
    ticker: str
    quantity: Decimal
    fees: Decimal
    order_id: str = ''
    note: str = ''

    order_count: ClassVar[int] = 0

    def __post_init__(self):
        Order.order_count += 1
        self.id = Order.order_count

    @property
    def price(self) -> Decimal:
        return self.amount / self.quantity


class Acquisition(Order):
    @property
    def total_cost(self) -> Decimal:
        return self.amount + self.fees

    def __hash__(self) -> int:
        return hash((self.timestamp, self.order_id))


class Disposal(Order):
    @property
    def net_proceeds(self) -> Decimal:
        return self.amount - self.fees

    def __hash__(self) -> int:
        return hash((self.timestamp, self.order_id))


@dataclass(kw_only=True)
class Dividend(Transaction):
    ticker: str
    withheld: Decimal

    def __hash__(self) -> int:
        return hash((self.timestamp, self.amount))


class Transfer(Transaction):
    def __hash__(self) -> int:
        return hash((self.timestamp, self.amount))


class Interest(Transaction):
    def __hash__(self) -> int:
        return hash((self.timestamp, self.amount))
