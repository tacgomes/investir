from abc import ABC
from dataclasses import dataclass
from datetime import datetime, date
from decimal import Decimal
from typing import ClassVar

from .utils import date_to_tax_year


@dataclass
class Transaction(ABC):
    timestamp: datetime
    amount: Decimal

    @property
    def date(self) -> date:
        return self.timestamp.date()

    def tax_year(self) -> int:
        return date_to_tax_year(self.date)


@dataclass(kw_only=True)
class Order(Transaction, ABC):
    id: int = 0
    ticker: str
    quantity: Decimal
    fees: Decimal = Decimal('0.0')
    order_id: str = ''
    note: str = ''

    order_count: ClassVar[int] = 0

    def __post_init__(self):
        Order.order_count += 1
        self.id = Order.order_count

    @property
    def price(self) -> Decimal:
        return self.amount / self.quantity

    def split(self, split_quantity: Decimal):  # -> tuple[Self, Self] (3.11+)
        assert self.quantity >= split_quantity

        match_amount = self.price * split_quantity
        match_quantity = split_quantity
        match_fees = self.fees / self.quantity * split_quantity

        remainder_amount = self.amount - match_amount
        remainder_quantity = self.quantity - match_quantity
        remainder_fees = self.fees - match_fees

        match = type(self)(
            self.timestamp,
            amount=match_amount,
            ticker=self.ticker,
            quantity=match_quantity,
            fees=match_fees,
            note=f'Splitted from order {self.id}')

        remainder = type(self)(
            self.timestamp,
            amount=remainder_amount,
            ticker=self.ticker,
            quantity=remainder_quantity,
            fees=remainder_fees,
            note=f'Splitted from order {self.id}')

        return match, remainder

    @staticmethod
    def merge(*orders: 'Order') -> 'Order':
        assert len(orders) > 1

        ticker = orders[0].ticker
        assert all(order.ticker == ticker for order in orders)

        order_class = type(orders[0])

        timestamp = orders[0].timestamp.replace(
            hour=0, minute=0, second=0, microsecond=0)

        amount = Decimal(sum(order.amount for order in orders))
        quantity = Decimal(sum(order.quantity for order in orders))
        fees = Decimal(sum(order.fees for order in orders))

        note = 'Merged from orders '
        note += ','.join(str(order.id) for order in orders)

        return order_class(
            timestamp,
            amount=amount,
            ticker=ticker,
            quantity=quantity,
            fees=fees,
            note=note)


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
