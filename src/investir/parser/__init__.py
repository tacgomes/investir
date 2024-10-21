from investir.parser.factory import ParserFactory
from investir.parser.freetrade import FreetradeParser
from investir.parser.trading212 import Trading212Parser

ParserFactory.register_parser(FreetradeParser)
ParserFactory.register_parser(Trading212Parser)
