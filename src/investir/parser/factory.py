from collections.abc import Callable
from pathlib import Path
from typing import ClassVar

from investir.parser.types import Parser


class ParserFactory:
    _parsers: ClassVar[dict[str, type[Parser]]] = {}

    @classmethod
    def register(cls, parser_name: str) -> Callable:
        def _wrapper(parser_class: type[Parser]) -> type[Parser]:
            cls._parsers[parser_name] = parser_class
            return parser_class

        return _wrapper

    @classmethod
    def create_parser(cls, csv_file: Path) -> tuple[Parser, str] | tuple[None, None]:
        for parser_name, parser_class in cls._parsers.items():
            parser = parser_class(csv_file)
            if parser.can_parse():
                return parser, parser_name

        return None, None
