import argparse
import importlib.metadata
import logging
import pathlib

from .config import Config
from .parser.factory import ParserFactory
from .transaction import TransactionType
from .transactionlog import TransactionLog

logger = logging.getLogger(__name__)


def path(parser: argparse.ArgumentParser, file: str) -> pathlib.Path:
    try:
        with open(file, encoding='utf-8'):
            pass
    except IOError as err:
        parser.error(str(err))
    return pathlib.Path(file)


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        'input_files',
        type=lambda file: path(parser, file),
        nargs='+',
        metavar='INPUT',
        help='Input CSV file with the transaction records'
    )

    parser.add_argument(
        '-d', '--debug',
        action='store_true',
        help='Enable debug logging')

    parser.add_argument(
        '-v', '--version',
        action='version',
        version=f'{parser.prog} v{importlib.metadata.version("investir")}',
    )

    parser.add_argument(
        '--tax-year',
        type=int,
        help='filter by tax year',
    )

    parser.add_argument(
        '--ticker',
        help='filter by a ticker',
    )

    tr_type_group = parser.add_mutually_exclusive_group()
    tr_type_group.add_argument(
        '--only-buys',
        action='store_const',
        dest='tr_type',
        const=TransactionType.ACQUISITION,
        help='show only acquisitions',
    )
    tr_type_group.add_argument(
        '--only-sells',
        action='store_const',
        dest='tr_type',
        const=TransactionType.DISPOSAL,
        help='show only disposals',
    )

    args = parser.parse_args()

    logging.basicConfig(
        format='[%(asctime)s] [%(levelname)-8s] %(message)s',
        level=logging.DEBUG if args.debug else logging.WARNING
    )

    config = Config(strict=True)

    trlog = TransactionLog()

    for csv_file in args.input_files:
        if csv_parser := ParserFactory.create_parser(csv_file, config):
            trlog.insert(csv_parser.parse())
        else:
            logger.warning('Failed to find a parser for %s', csv_file)

    trlog.show(args.tax_year, args.ticker, args.tr_type)
