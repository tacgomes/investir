import argparse
import importlib.metadata
import logging
import pathlib

from .config import Config
from .parser.factory import ParserFactory
from .transaction import OrderType, TransferType
from .transactionlog import TransactionLog

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
        const=OrderType.ACQUISITION,
        help='show only acquisitions',
    )
    type_group.add_argument(
        '--disposals',
        action='store_const',
        dest='order_type',
        const=OrderType.DISPOSAL,
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
        dest='transfer_type',
        const=TransferType.DEPOSIT,
        help='show only acquisitions',
    )
    type_group.add_argument(
        '--widthdraws',
        action='store_const',
        dest='transfer_type',
        const=TransferType.WITHDRAW,
        help='show only disposals'
    )


def create_interest_command(subparser, parent_parser) -> None:
    subparser.add_parser(
        'interest',
        help='show interest earned on cash',
        parents=[parent_parser])


def main() -> None:
    parser = argparse.ArgumentParser()

    subparser = parser.add_subparsers(
        dest='command',
        required=True)

    parent_parser = argparse.ArgumentParser(add_help=False)
    parent_parser.add_argument(
        '--tax-year',
        type=int,
        help='filter by tax year')

    create_orders_command(subparser, parent_parser)
    create_dividends_command(subparser, parent_parser)
    create_transfers_command(subparser, parent_parser)
    create_interest_command(subparser, parent_parser)

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

    args = parser.parse_args()

    logging.basicConfig(
        format='[%(asctime)s] [%(levelname)-8s] %(message)s',
        level=logging.DEBUG if args.debug else logging.WARNING
    )

    config = Config(strict=True)

    trlog = TransactionLog()

    for csv_file in args.input_files:
        if csv_parser := ParserFactory.create_parser(csv_file, config):
            result = csv_parser.parse()
            trlog.insert_orders(result.orders)
            trlog.insert_dividends(result.dividends)
            trlog.insert_transfers(result.transfers)
            trlog.insert_interest(result.interest)
        else:
            logger.warning('Failed to find a parser for %s', csv_file)

    filters = []

    if hasattr(args, 'ticker') and args.ticker is not None:
        filters.append(lambda tr: tr.ticker == args.ticker)

    if hasattr(args, 'order_type') and args.order_type is not None:
        filters.append(lambda tr: tr.type == args.order_type)

    if args.tax_year is not None:
        filters.append(lambda tr: tr.tax_year() == args.tax_year)

    if args.command == 'orders':
        trlog.show_orders(filters)
    elif args.command == 'dividends':
        trlog.show_dividends(filters)
    elif args.command == 'transfers':
        trlog.show_transfers(filters)
    elif args.command == 'interest':
        trlog.show_interest(filters)
