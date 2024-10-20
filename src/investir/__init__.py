from investir.parser import ParserFactory
from investir.parsers.freetrade import FreetradeParser
from investir.parsers.trading212 import Trading212Parser

ParserFactory.register_parser(FreetradeParser)
ParserFactory.register_parser(Trading212Parser)
