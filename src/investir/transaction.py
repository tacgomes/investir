from enum import Enum
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


class TransactionType(Enum):
    ACQUISITION = 1
    DISPOSAL = 2


@dataclass
class Transaction:
    timestamp: datetime
    ticker: str
    type: TransactionType
    price: Decimal
    quantity: Decimal
    fees: Decimal
    order_id: str

    def total_amount(self) -> Decimal:
        amount = self.price * self.quantity
        if self.type == TransactionType.ACQUISITION:
            amount += self.fees
        else:
            amount -= self.fees
        return amount

    def __hash__(self) -> int:
        return hash((self.order_id))
