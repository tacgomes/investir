import importlib.metadata
import logging
import operator
from collections.abc import Callable, Sequence
from datetime import datetime
from pathlib import Path
from typing import Annotated, Optional

import click
import typer

from .config import config
from .exceptions import InvestirError
from .logging import configure_logger
from .parser import ParserFactory
from .securitiesdatacache import SecuritiesDataCache
from .securitiesdataprovider import (
    NoopDataProvider,
    SecuritiesDataProvider,
    YahooFinanceDataProvider,
)
from .taxcalculator import TaxCalculator
from .transaction import Acquisition, Disposal, Transaction
from .trhistory import TrHistory
from .typing import Ticker, Year

logger = logging.getLogger(__name__)


class OrderedCommands(typer.core.TyperGroup):
    def list_commands(self, ctx: click.Context) -> list[str]:
        return list(self.commands.keys())


class MutuallyExclusiveOption(click.exceptions.UsageError):
    def __init__(self, opt1: str, opt2: str) -> None:
        super().__init__(f"Option {opt1} cannot be used together with option {opt2}")


app = typer.Typer(
    cls=OrderedCommands,
    context_settings={"help_option_names": ["-h", "--help"]},
    no_args_is_help=True,
)

FilesArg = Annotated[
    list[Path],
    typer.Argument(
        exists=True,
        dir_okay=False,
        readable=True,
        help="CSV files with the account activity.",
        show_default=False,
    ),
]

TaxYearOpt = Annotated[
    Optional[int],
    typer.Option(
        min=2008,
        max=datetime.now().year,
        metavar="TAX-YEAR",
        help="Filter by tax year.",
        show_default=False,
    ),
]

TickerOpt = Annotated[
    Optional[str],
    typer.Option(metavar="TICKER", help="Filter by ticker.", show_default=False),
]


def parse(input_files: list[Path]) -> tuple[TrHistory, TaxCalculator]:
    orders = []
    dividends = []
    transfers = []
    interest = []

    def abort(message: str) -> None:
        logging.critical(message)
        raise typer.Exit(code=1)

    for path in input_files:
        logging.info("Parsing input file: %s", path)
        if parser := ParserFactory.create_parser(path):
            try:
                result = parser.parse()
            except InvestirError as ex:
                abort(str(ex))
            logging.info(
                "Parsed: "
                "%s orders, %s dividend payments, %s transfers, %s interest payments",
                len(result.orders),
                len(result.dividends),
                len(result.transfers),
                len(result.interest),
            )

            orders += result.orders
            dividends += result.dividends
            transfers += result.transfers
            interest += result.interest
        else:
            abort(f"Unable to find a parser for {path}")

    tr_hist = TrHistory(
        orders=orders, dividends=dividends, transfers=transfers, interest=interest
    )

    logging.info(
        "Total: %s orders, %s dividend payments, %s transfers, %s interest payments",
        len(tr_hist.orders),
        len(tr_hist.dividends),
        len(tr_hist.transfers),
        len(tr_hist.interest),
    )

    try:
        data_provider: SecuritiesDataProvider
        if not config.offline:
            data_provider = YahooFinanceDataProvider()
        else:
            data_provider = NoopDataProvider()
        securities_data = SecuritiesDataCache(data_provider, tr_hist)
        tax_calculator = TaxCalculator(tr_hist, securities_data)
    except InvestirError as ex:
        abort(str(ex))

    return tr_hist, tax_calculator


def create_filters(
    tax_year: int | None = None,
    ticker: str | None = None,
    tr_type: type[Transaction] | None = None,
    amount_op: Callable | None = None,
) -> Sequence[Callable[[Transaction], bool]]:
    filters = []

    if tax_year is not None:
        filters.append(lambda tr: tr.tax_year() == Year(tax_year))

    if ticker is not None:
        filters.append(lambda tr: tr.ticker == ticker)

    if tr_type is not None:
        filters.append(lambda tr: isinstance(tr, tr_type))

    if amount_op is not None:
        filters.append(lambda tr: amount_op(tr.amount, 0.0))

    return filters


def version_callback(value: bool):
    if value:
        print(f"v{importlib.metadata.version('investir')}")
        raise typer.Exit()


@app.callback()
def main_callback(  # pylint: disable=too-many-arguments,unused-argument
    strict: Annotated[
        bool, typer.Option(help="Abort if data integrity issues are found.")
    ] = True,
    offline: Annotated[
        bool,
        typer.Option(
            "--offline",
            help=(
                "Disable fetching additional data about securities (e.g. list of "
                "share sub-division events) from the Internet."
            ),
        ),
    ] = False,
    include_fx_fees: Annotated[
        bool, typer.Option(help="Include foreign exchange fees as an allowable cost.")
    ] = True,
    verbose: Annotated[
        bool, typer.Option("--verbose", help="Enable additional logging.")
    ] = False,
    quiet: Annotated[
        bool, typer.Option("--quiet", help="Disable all non-critical logging.")
    ] = False,
    colour: Annotated[bool, typer.Option(help="Show coloured output.")] = True,
    version: Annotated[
        Optional[bool],
        typer.Option(
            "--version",
            callback=version_callback,
            help="Show version information and exit.",
        ),
    ] = None,
) -> None:
    if verbose and quiet:
        raise MutuallyExclusiveOption("--verbose", "--quiet")

    config.strict = strict
    config.offline = offline
    config.include_fx_fees = include_fx_fees

    if quiet:
        config.log_level = logging.CRITICAL
    elif verbose:
        config.log_level = logging.DEBUG

    config.use_colour = colour

    configure_logger()


@app.command("orders")
def orders_command(
    files: FilesArg,
    tax_year: TaxYearOpt = None,
    ticker: TickerOpt = None,
    acquisitions_only: Annotated[
        bool, typer.Option("--acquisitions", help="Show only acquisitions.")
    ] = False,
    disposals_only: Annotated[
        bool, typer.Option("--disposals", help="Show only disposals.")
    ] = False,
) -> None:
    """
    Show share buy/sell orders.
    """
    if acquisitions_only and disposals_only:
        raise MutuallyExclusiveOption("--acquisitions", "--disposals")

    tr_hist, _ = parse(files)

    tr_type: type[Transaction] | None = None
    if acquisitions_only:
        tr_type = Acquisition
    elif disposals_only:
        tr_type = Disposal

    filters = create_filters(tax_year=tax_year, ticker=ticker, tr_type=tr_type)
    tr_hist.show_orders(filters)


@app.command("dividends")
def dividends_command(
    files: FilesArg,
    tax_year: TaxYearOpt = None,
    ticker: TickerOpt = None,
) -> None:
    """
    Show share dividends paid out.
    """
    tr_hist, _ = parse(files)
    filters = create_filters(tax_year=tax_year, ticker=ticker)
    tr_hist.show_dividends(filters)


@app.command("transfers")
def transfers_command(
    files: FilesArg,
    tax_year: TaxYearOpt = None,
    deposits_only: Annotated[
        bool, typer.Option("--deposits", help="Show only deposits.")
    ] = False,
    withdrawals_only: Annotated[
        bool, typer.Option("--withdrawals", help="Show only withdrawals.")
    ] = False,
) -> None:
    """
    Show cash deposits and cash withdrawals.
    """
    if deposits_only and withdrawals_only:
        raise MutuallyExclusiveOption("--deposits", "--withdrawals")

    tr_hist, _ = parse(files)

    if deposits_only:
        amount_op = operator.gt
    elif withdrawals_only:
        amount_op = operator.lt
    else:
        amount_op = None

    filters = create_filters(tax_year=tax_year, amount_op=amount_op)
    tr_hist.show_transfers(filters)


@app.command("interest")
def interest_command(files: FilesArg, tax_year: TaxYearOpt = None) -> None:
    """
    Show interest earned on cash.
    """
    tr_hist, _ = parse(files)
    filters = create_filters(tax_year=tax_year)
    tr_hist.show_interest(filters)


@app.command("capital-gains")
def capital_gains_command(
    files: FilesArg,
    gains_only: Annotated[
        bool, typer.Option("--gains", help="Show only capital gains.")
    ] = False,
    losses_only: Annotated[
        bool, typer.Option("--losses", help="Show only capital losses.")
    ] = False,
    tax_year: TaxYearOpt = None,
    ticker: TickerOpt = None,
) -> None:
    """
    Show capital gains report.
    """
    if gains_only and losses_only:
        raise MutuallyExclusiveOption("--gains", "--losses")

    _, tax_calculator = parse(files)
    tax_year = Year(tax_year) if tax_year else None
    ticker = Ticker(ticker) if ticker else None
    tax_calculator.show_capital_gains(tax_year, ticker, gains_only, losses_only)


@app.command("holdings")
def holdings_command(files: FilesArg, ticker: TickerOpt = None) -> None:
    """
    Show current holdings.
    """
    _, tax_calculator = parse(files)
    ticker = Ticker(ticker) if ticker else None
    tax_calculator.show_holdings(ticker)


def main() -> None:
    app()
