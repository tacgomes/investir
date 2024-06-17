from .parser import ParserFactory
from .parsers.freetrade import FreetradeParser
from .parsers.trading212 import Trading212Parser

ParserFactory.register_parser(FreetradeParser)
ParserFactory.register_parser(Trading212Parser)
