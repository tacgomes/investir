import logging

from pathlib import Path

from ..config import Config
from .parser import Parser

logger = logging.getLogger(__name__)


class ParserFactory:
    _parsers: list[Parser] = []

    @classmethod
    def register_parser(cls, parser) -> None:
        cls._parsers.append(parser)

    @classmethod
    def create_parser(cls, filename: Path, config: Config) -> Parser | None:
        for parser_class in cls._parsers:
            parser = parser_class(filename, config)  # type: ignore[operator]
            if parser.can_parse():
                logger.info('Found parser for %s: %s', filename, parser.name())
                return parser

        return None
