import argparse
import importlib.metadata
import logging
import pathlib

from .config import Config
from .logging import setup_logging
from .parser.factory import ParserFactory
from .transaction import Acquisition, Disposal
from .trhistory import TrHistory

logger = logging.getLogger(__name__)


def path(parser: argparse.ArgumentParser, file: str) -> pathlib.Path:
    try:
        with open(file, encoding='utf-8'):
            pass
    except IOError as err:
        parser.error(str(err))
    return pathlib.Path(file)


def create_orders_command(subparser, parent_parser) -> None:
    parser = subparser.add_parser(
        'orders',
        help='show share buy/sell orders',
        parents=[parent_parser])

    parser.add_argument(
        '--ticker',
        help='filter by a ticker',
        dest='ticker'
    )

    type_group = parser.add_mutually_exclusive_group()
    type_group.add_argument(
        '--acquisitions',
        action='store_const',
        dest='order_type',
        const=Acquisition,
        help='show only acquisitions',
    )
    type_group.add_argument(
        '--disposals',
        action='store_const',
        dest='order_type',
        const=Disposal,
        help='show only disposals',
    )


def create_dividends_command(subparser, parent_parser) -> None:
    parser = subparser.add_parser(
        'dividends',
        help='show share dividends',
        parents=[parent_parser])

    parser.add_argument(
        '--ticker',
        help='filter by a ticker',
        dest='ticker'
    )


def create_transfers_command(subparser, parent_parser) -> None:
    parser = subparser.add_parser(
        'transfers',
        help='show cash transfers',
        parents=[parent_parser])

    type_group = parser.add_mutually_exclusive_group()
    type_group.add_argument(
        '--deposits',
        action='store_const',
        dest='amount_filter',
        const=lambda tr: tr.amount > 0.0,
        help='show only acquisitions',
    )
    type_group.add_argument(
        '--widthdraws',
        action='store_const',
        dest='amount_filter',
        const=lambda tr: tr.amount < 0.0,
        help='show only disposals'
    )


def create_interest_command(subparser, parent_parser) -> None:
    subparser.add_parser(
        'interest',
        help='show interest earned on cash',
        parents=[parent_parser])


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='enable verbose logging')

    parser.add_argument(
        '--no-colour',
        action='store_false',
        dest='colour',
        default=True,
        help='disable coloured output')

    parser.add_argument(
        '-v', '--version',
        action='version',
        version=f'{parser.prog} v{importlib.metadata.version("investir")}',
    )

    parent_parser = argparse.ArgumentParser(add_help=False)

    parent_parser.add_argument(
        '--tax-year',
        type=int,
        help='filter by tax year')

    parent_parser.add_argument(
        'input_files',
        type=lambda file: path(parser, file),
        nargs='+',
        metavar='INPUT',
        help='input CSV file with the transaction records'
    )

    subparser = parser.add_subparsers(dest='command', required=True)
    create_orders_command(subparser, parent_parser)
    create_dividends_command(subparser, parent_parser)
    create_transfers_command(subparser, parent_parser)
    create_interest_command(subparser, parent_parser)

    args = parser.parse_args()

    setup_logging(args.verbose, args.colour)

    config = Config(strict=True)

    tr_hist = TrHistory()

    for csv_file in args.input_files:
        if csv_parser := ParserFactory.create_parser(csv_file, config):
            result = csv_parser.parse()
            tr_hist.insert_orders(result.orders)
            tr_hist.insert_dividends(result.dividends)
            tr_hist.insert_transfers(result.transfers)
            tr_hist.insert_interest(result.interest)
        else:
            logger.warning('Failed to find a parser for %s', csv_file)

    filters = []

    if hasattr(args, 'ticker') and args.ticker is not None:
        filters.append(lambda tr: tr.ticker == args.ticker)

    if hasattr(args, 'order_type') and args.order_type is not None:
        filters.append(lambda tr: isinstance(tr, args.order_type))

    if args.tax_year is not None:
        filters.append(lambda tr: tr.tax_year() == args.tax_year)

    if args.command == 'orders':
        tr_hist.show_orders(filters)
    elif args.command == 'dividends':
        tr_hist.show_dividends(filters)
    elif args.command == 'transfers':
        tr_hist.show_transfers(filters)
    elif args.command == 'interest':
        tr_hist.show_interest(filters)
