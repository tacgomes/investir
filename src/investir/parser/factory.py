import logging
from pathlib import Path
from typing import ClassVar

from investir.parser.types import Parser

logger = logging.getLogger(__name__)


class ParserFactory:
    _parsers: ClassVar[list[type[Parser]]] = []

    @classmethod
    def register_parser(cls, parser: type[Parser]) -> None:
        cls._parsers.append(parser)

    @classmethod
    def create_parser(cls, csv_file: Path) -> Parser | None:
        for parser_class in cls._parsers:
            parser = parser_class(csv_file)
            if parser.can_parse():
                logger.info("Found parser: %s", type(parser).name())
                return parser

        return None
