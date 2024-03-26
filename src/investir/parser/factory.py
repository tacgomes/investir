import logging

logger = logging.getLogger(__name__)


class ParserFactory:
    _parsers = []

    @classmethod
    def register_parser(cls, parser):
        cls._parsers.append(parser)

    @classmethod
    def create_parser(cls, filename, config):
        for parser_class in cls._parsers:
            parser = parser_class(filename, config)
            if parser.can_parse():
                logger.info('Found parser for %s: %s', filename, parser.name())
                return parser

        return None
