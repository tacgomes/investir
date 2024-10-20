import logging
from pathlib import Path
from typing import ClassVar, NamedTuple, Protocol

from .transaction import Dividend, Interest, Order, Transfer

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


class ParserFactory:
    _parsers: ClassVar[list[type[Parser]]] = []

    @classmethod
    def register_parser(cls, parser: type[Parser]) -> None:
        cls._parsers.append(parser)

    @classmethod
    def create_parser(cls, filename: Path) -> Parser | None:
        for parser_class in cls._parsers:
            parser = parser_class(filename)  # type: ignore[call-arg]
            if parser.can_parse():
                logger.info("Found parser: %s", type(parser).name())
                return parser

        return None
