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
