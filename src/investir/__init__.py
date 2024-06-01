from .parser import ParserFactory
from .parsers.freetrade import FreetradeParser

ParserFactory.register_parser(FreetradeParser)
