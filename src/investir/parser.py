import logging

from abc import ABC, abstractmethod
from pathlib import Path
from typing import NamedTuple

from .transaction import Order, Dividend, Transfer, Interest


logger = logging.getLogger(__name__)


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


class ParserFactory:
    _parsers: list[Parser] = []

    @classmethod
    def register_parser(cls, parser) -> None:
        cls._parsers.append(parser)

    @classmethod
    def create_parser(cls, filename: Path) -> Parser | None:
        for parser_class in cls._parsers:
            parser = parser_class(filename)  # type: ignore[operator]
            if parser.can_parse():
                logger.info("Found parser: %s", type(parser).name())
                return parser

        return None
