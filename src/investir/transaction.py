import datetime

from enum import Enum
from dataclasses import dataclass
from decimal import Decimal


class TransactionType(Enum):
    ACQUISITION = 1
    DISPOSAL = 2


@dataclass
class Transaction:
    timestamp: datetime.time
    ticker: str
    type: TransactionType
    price: Decimal
    quantity: Decimal
    fees: Decimal
