import logging
from typing import NamedTuple, Protocol

from investir.transaction import Dividend, Interest, Order, Transfer

logger = logging.getLogger(__name__)


class ParsingResult(NamedTuple):
    orders: list[Order]
    dividends: list[Dividend]
    transfers: list[Transfer]
    interest: list[Interest]


class Parser(Protocol):
    @staticmethod
    def name() -> str:
        pass

    def can_parse(self) -> bool:
        pass

    def parse(self) -> ParsingResult:
        pass
