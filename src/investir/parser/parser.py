from abc import ABC, abstractmethod
from typing import NamedTuple

from ..transaction import Order, Dividend, Transfer, Interest


class ParsingResult(NamedTuple):
    orders: list[Order]
    dividends: list[Dividend]
    transfers: list[Transfer]
    interest: list[Interest]


class Parser(ABC):
    @staticmethod
    @abstractmethod
    def name() -> str:
        pass

    @abstractmethod
    def can_parse(self) -> bool:
        pass

    @abstractmethod
    def parse(self) -> ParsingResult:
        pass
