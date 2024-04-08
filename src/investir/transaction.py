from enum import Enum
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from .utils import date_to_tax_year


class OrderType(Enum):
    ACQUISITION = 1
    DISPOSAL = 2


class TransferType(Enum):
    DEPOSIT = 1
    WITHDRAW = 2


@dataclass
class Order:
    timestamp: datetime
    ticker: str
    type: OrderType
    price: Decimal
    quantity: Decimal
    fees: Decimal
    order_id: str

    def total_amount(self) -> Decimal:
        amount = self.price * self.quantity
        if self.type == OrderType.ACQUISITION:
            amount += self.fees
        else:
            amount -= self.fees
        return amount

    def tax_year(self) -> int:
        return date_to_tax_year(self.timestamp.date())

    def __hash__(self) -> int:
        return hash(self.order_id)


@dataclass
class Dividend:
    timestamp: datetime
    ticker: str
    amount: Decimal
    withheld: Decimal

    def tax_year(self) -> int:
        return date_to_tax_year(self.timestamp.date())

    def __hash__(self) -> int:
        return hash(self.timestamp) + hash(self.amount)


@dataclass
class Transfer:
    timestamp: datetime
    type: TransferType
    amount: Decimal

    def tax_year(self) -> int:
        return date_to_tax_year(self.timestamp.date())

    def __hash__(self) -> int:
        return hash(self.timestamp) + hash(self.amount)


@dataclass
class Interest:
    timestamp: datetime
    amount: Decimal

    def tax_year(self) -> int:
        return date_to_tax_year(self.timestamp.date())

    def __hash__(self) -> int:
        return hash(self.timestamp) + hash(self.amount)
