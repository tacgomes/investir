import argparse
import importlib.metadata
import logging
import pathlib
import sys

from .config import config
from .exceptions import InvestirError
from .logging import setup_logging
from .parser.factory import ParserFactory
from .taxcalculator import TaxCalculator
from .transaction import Acquisition, Disposal
from .trhistory import TrHistory

logger = logging.getLogger(__name__)


def path(parser: argparse.ArgumentParser, file: str) -> pathlib.Path:
    try:
        with open(file, encoding="utf-8"):
            pass
    except IOError as err:
        parser.error(str(err))
    return pathlib.Path(file)


def create_orders_command(subparser, parent_parser) -> None:
    parser = subparser.add_parser(
        "orders", help="show share buy/sell orders", parents=[parent_parser]
    )

    parser.add_argument("--ticker", help="filter by a ticker", dest="ticker")

    type_group = parser.add_mutually_exclusive_group()
    type_group.add_argument(
        "--acquisitions",
        action="store_const",
        dest="order_type",
        const=Acquisition,
        help="show only acquisitions",
    )
    type_group.add_argument(
        "--disposals",
        action="store_const",
        dest="order_type",
        const=Disposal,
        help="show only disposals",
    )


def create_dividends_command(subparser, parent_parser) -> None:
    parser = subparser.add_parser(
        "dividends", help="show share dividends", parents=[parent_parser]
    )

    parser.add_argument("--ticker", help="filter by a ticker", dest="ticker")


def create_transfers_command(subparser, parent_parser) -> None:
    parser = subparser.add_parser(
        "transfers", help="show cash transfers", parents=[parent_parser]
    )

    type_group = parser.add_mutually_exclusive_group()
    type_group.add_argument(
        "--deposits",
        action="store_const",
        dest="amount_filter",
        const=lambda tr: tr.amount > 0.0,
        help="show only acquisitions",
    )
    type_group.add_argument(
        "--widthdraws",
        action="store_const",
        dest="amount_filter",
        const=lambda tr: tr.amount < 0.0,
        help="show only disposals",
    )


def create_interest_command(subparser, parent_parser) -> None:
    subparser.add_parser(
        "interest", help="show interest earned on cash", parents=[parent_parser]
    )


def create_tax_command(subparser, parent_parser) -> None:
    parser = subparser.add_parser(
        "capital-gains", help="show capital gains report", parents=[parent_parser]
    )

    parser.add_argument("--ticker", help="filter by a ticker", dest="ticker")

    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--gains",
        action="store_true",
        dest="gains_only",
        help="show only capital gains",
    )
    group.add_argument(
        "--losses",
        action="store_true",
        dest="losses_only",
        help="show only capital losses",
    )


def create_holdings_command(subparser, parent_parser) -> None:
    parser = subparser.add_parser(
        "holdings", help="show holdings", parents=[parent_parser]
    )

    parser.add_argument("--ticker", help="filter by a ticker")

    parser.add_argument(
        "--show-avg-cost", action="store_true", help="show the average cost per share"
    )


def parse_input_files(args: argparse.Namespace, tr_hist: TrHistory) -> None:
    for csv_file in args.input_files:
        if csv_parser := ParserFactory.create_parser(csv_file):
            try:
                result = csv_parser.parse()
            except InvestirError as ex:
                logger.error(ex)
                sys.exit(1)
            tr_hist.insert_orders(result.orders)
            tr_hist.insert_dividends(result.dividends)
            tr_hist.insert_transfers(result.transfers)
            tr_hist.insert_interest(result.interest)
        else:
            logger.warning("Failed to find a parser for %s", csv_file)


def run_command(args: argparse.Namespace, tr_hist: TrHistory) -> None:
    filters = []

    if hasattr(args, "ticker") and args.ticker is not None:
        filters.append(lambda tr: tr.ticker == args.ticker)

    if hasattr(args, "order_type") and args.order_type is not None:
        filters.append(lambda tr: isinstance(tr, args.order_type))

    if hasattr(args, "amount_filter") and args.amount_filter is not None:
        filters.append(args.amount_filter)

    if args.tax_year is not None:
        filters.append(lambda tr: tr.tax_year() == args.tax_year)

    try:
        tax_calc = TaxCalculator(tr_hist)
    except InvestirError as ex:
        logger.error(ex)
        sys.exit(1)

    match args.command:
        case "orders":
            tr_hist.show_orders(filters)
        case "dividends":
            tr_hist.show_dividends(filters)
        case "transfers":
            tr_hist.show_transfers(filters)
        case "interest":
            tr_hist.show_interest(filters)
        case "capital-gains":
            tax_calc.show_capital_gains(
                args.tax_year, args.ticker, args.gains_only, args.losses_only
            )
        case "holdings":
            tax_calc.show_holdings(args.ticker, args.show_avg_cost)
        case _:
            raise AssertionError(f"Unknown command: {args.command}")


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--no-strict",
        action="store_false",
        dest="strict",
        default=True,
        help="disable aborting the program when encountering certain errors",
    )

    parser.add_argument("--verbose", action="store_true", help="enable verbose logging")

    parser.add_argument(
        "--no-colour",
        action="store_false",
        dest="colour",
        default=True,
        help="disable coloured output",
    )

    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f'{parser.prog} v{importlib.metadata.version("investir")}',
    )

    parent_parser = argparse.ArgumentParser(add_help=False)

    parent_parser.add_argument("--tax-year", type=int, help="filter by tax year")

    parent_parser.add_argument(
        "input_files",
        type=lambda file: path(parser, file),
        nargs="+",
        metavar="INPUT",
        help="input CSV file with the transaction records",
    )

    subparser = parser.add_subparsers(dest="command", required=True)
    create_orders_command(subparser, parent_parser)
    create_dividends_command(subparser, parent_parser)
    create_transfers_command(subparser, parent_parser)
    create_interest_command(subparser, parent_parser)
    create_tax_command(subparser, parent_parser)
    create_holdings_command(subparser, parent_parser)

    args = parser.parse_args()
    config.strict = args.strict
    tr_hist = TrHistory()

    setup_logging(args.verbose, args.colour)
    parse_input_files(args, tr_hist)
    run_command(args, tr_hist)
