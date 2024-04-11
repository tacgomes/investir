from .factory import ParserFactory
from .freetrade import FreetradeParser

ParserFactory.register_parser(FreetradeParser)
