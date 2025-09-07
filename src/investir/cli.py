import importlib.metadata
import logging
import operator
from collections.abc import Callable, Sequence
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Annotated, Optional

import click
import typer

from investir.config import config
from investir.exceptions import InvestirError
from investir.findata import (
    FinancialData,
    HistoricalExchangeRateProvider,
    HmrcMonthlyExhangeRateProvider,
    LocalHistoricalExchangeRateProvider,
    YahooFinanceHistoricalExchangeRateProvider,
    YahooFinanceLiveExchangeRateProvider,
    YahooFinanceSecurityInfoProvider,
)
from investir.logging import configure_logger
from investir.output import OutputGenerator
from investir.parser import ParserFactory
from investir.prettytable import OutputFormat
from investir.taxcalculator import TaxCalculator
from investir.transaction import Acquisition, Disposal, Transaction
from investir.trhistory import TransactionHistory
from investir.typing import TaxYear, Ticker

logger = logging.getLogger(__name__)


class OrderedCommands(typer.core.TyperGroup):
    def list_commands(self, ctx: click.Context) -> list[str]:
        return list(self.commands.keys())


class MutuallyExclusiveOption(click.exceptions.UsageError):
    def __init__(self, opt1: str, opt2: str) -> None:
        super().__init__(f"Option {opt1} cannot be used together with option {opt2}")


class RatesProvider(str, Enum):
    YAHOO_FINANCE = "yahoo-finance"
    HMRC_MONTHLY = "hmrc-monthly"


app = typer.Typer(
    cls=OrderedCommands,
    context_settings={"help_option_names": ["-h", "--help"]},
    no_args_is_help=True,
    pretty_exceptions_enable=False,
)

FilesArg = Annotated[
    list[Path],
    typer.Argument(
        exists=True,
        dir_okay=False,
        help="CSV files with the account activity.",
        show_default=False,
    ),
]

TaxYearOpt = Annotated[
    Optional[int],
    typer.Option(
        min=2009,
        max=datetime.now().year + 1,
        metavar="TAX-YEAR",
        help="Filter by tax year (e.g. Use 2025 to view the transactions "
        "made in the 2024-2025 tax year).",
        show_default=False,
    ),
]

TickerOpt = Annotated[
    Optional[str],
    typer.Option(metavar="TICKER", help="Filter by ticker.", show_default=False),
]

IncludeFxFeesOpt = Annotated[
    bool, typer.Option(help="Include foreign exchange fees as an allowable cost.")
]

RatesProviderOpt = Annotated[
    RatesProvider,
    typer.Option(
        "--rates-provider",
        help="Online provider for historical exchange rates. "
        "This option is ignored if --rates-file is also used.",
    ),
]

RatesFileOpt = Annotated[
    Optional[Path],
    typer.Option(
        exists=True, dir_okay=False, help="File with historical exchange rates."
    ),
]

OutputFormatOpt = Annotated[
    OutputFormat,
    typer.Option("--output", "-o", help="Output format."),
]


def abort(msg: InvestirError | str) -> None:
    logger.critical(str(msg))
    if isinstance(msg, InvestirError) and msg.skippable:
        option = typer.style("--no-strict", fg=typer.colors.CYAN, bold=True)
        print(f"\nUse the {option} option to ignore this error.")
    raise typer.Exit(code=1)


def parse(input_files: Sequence[Path]) -> TransactionHistory:
    orders = []
    dividends = []
    transfers = []
    interest = []

    for path in input_files:
        parser, parser_name = ParserFactory.create_parser(path)
        if parser:
            logger.info("Parsing '%s' with %s parser", path, parser_name)
            try:
                result = parser.parse()
            except InvestirError as ex:
                abort(ex)

            logger.info(
                "Parsed "
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
            abort(f"Unable to find a parser for '{path}'")

    trhistory = TransactionHistory(
        orders=orders, dividends=dividends, transfers=transfers, interest=interest
    )

    if len(input_files) >= 2:
        logger.info(
            "Total: "
            "%s orders, %s dividend payments, %s transfers, %s interest payments",
            len(trhistory.orders),
            len(trhistory.dividends),
            len(trhistory.transfers),
            len(trhistory.interest),
        )

    return trhistory


def make_output_generator(
    trhistory: TransactionHistory, ctx: typer.Context
) -> OutputGenerator:
    security_info_provider = YahooFinanceSecurityInfoProvider()
    live_rates_provider = YahooFinanceLiveExchangeRateProvider()
    historical_rates_provider: HistoricalExchangeRateProvider

    if (rates_file := ctx.params.get("rates_file")) is not None:  # pragma: no cover
        historical_rates_provider = LocalHistoricalExchangeRateProvider(
            Path(rates_file)
        )
    else:
        match ctx.params.get("rates_provider"):
            case RatesProvider.YAHOO_FINANCE | None:
                historical_rates_provider = YahooFinanceHistoricalExchangeRateProvider()
            case RatesProvider.HMRC_MONTHLY:  #  pragma: no cover
                historical_rates_provider = HmrcMonthlyExhangeRateProvider()

    findata = FinancialData(
        security_info_provider, live_rates_provider, historical_rates_provider
    )
    taxcalc = TaxCalculator(trhistory, findata)

    return OutputGenerator(trhistory, taxcalc)


def create_filters(
    tax_year: int | None = None,
    ticker: str | None = None,
    tr_type: type[Transaction] | None = None,
    total_op: Callable | None = None,
) -> Sequence[Callable[[Transaction], bool]]:
    filters = []

    if tax_year is not None:
        filters.append(lambda tr: tr.tax_year() == TaxYear(tax_year))

    if ticker is not None:
        filters.append(lambda tr: tr.ticker == ticker)

    if tr_type is not None:
        filters.append(lambda tr: isinstance(tr, tr_type))

    if total_op is not None:
        filters.append(lambda tr: total_op(tr.total.amount, 0.0))

    return filters


def version_callback(value: bool) -> None:
    if value:
        print(f"{__package__} {importlib.metadata.version(__package__)}")
        raise typer.Exit()


@app.callback()
def main_callback(
    strict: Annotated[
        bool, typer.Option(help="Abort if data integrity issues are found.")
    ] = config.strict,
    offline: Annotated[
        bool,
        typer.Option(
            "--offline",
            help=(
                "Disable fetching additional data about securities (e.g. list of "
                "share sub-division events) from the Internet."
            ),
        ),
    ] = config.offline,
    cache_dir: Annotated[
        Path,
        typer.Option(
            file_okay=False,
            help=(
                "Location where to store cache files with securities information "
                "and foreign exchange rates downloaded from the Internet."
            ),
        ),
    ] = config.cache_dir,
    verbose: Annotated[
        bool, typer.Option("--verbose", help="Enable additional logging.")
    ] = False,
    quiet: Annotated[
        bool, typer.Option("--quiet", help="Disable all non-critical logging.")
    ] = False,
    colour: Annotated[
        bool, typer.Option(help="Show coloured output.")
    ] = config.use_colour,
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
    config.cache_dir = cache_dir

    if quiet:
        config.log_level = logging.CRITICAL

    if verbose:
        config.log_level = logging.DEBUG

    config.use_colour = colour

    configure_logger()


@app.command("orders")
def orders_command(
    ctx: typer.Context,
    files: FilesArg,
    tax_year: TaxYearOpt = None,
    ticker: TickerOpt = None,
    acquisitions_only: Annotated[
        bool, typer.Option("--acquisitions", help="Show only acquisitions.")
    ] = False,
    disposals_only: Annotated[
        bool, typer.Option("--disposals", help="Show only disposals.")
    ] = False,
    format: OutputFormatOpt = OutputFormat.TEXT,
) -> None:
    """
    Show share buy/sell orders.
    """
    if acquisitions_only and disposals_only:
        raise MutuallyExclusiveOption("--acquisitions", "--disposals")

    tr_type: type[Transaction] | None = None
    if acquisitions_only:
        tr_type = Acquisition
    elif disposals_only:
        tr_type = Disposal

    filters = create_filters(tax_year=tax_year, ticker=ticker, tr_type=tr_type)
    outputter = make_output_generator(parse(files), ctx)
    outputter.show_orders(format, filters)


@app.command("dividends")
def dividends_command(
    ctx: typer.Context,
    files: FilesArg,
    tax_year: TaxYearOpt = None,
    ticker: TickerOpt = None,
    format: OutputFormatOpt = OutputFormat.TEXT,
) -> None:
    """
    Show share dividends paid out.
    """
    filters = create_filters(tax_year=tax_year, ticker=ticker)
    outputter = make_output_generator(parse(files), ctx)
    outputter.show_dividends(format, filters)


@app.command("transfers")
def transfers_command(
    ctx: typer.Context,
    files: FilesArg,
    tax_year: TaxYearOpt = None,
    deposits_only: Annotated[
        bool, typer.Option("--deposits", help="Show only deposits.")
    ] = False,
    withdrawals_only: Annotated[
        bool, typer.Option("--withdrawals", help="Show only withdrawals.")
    ] = False,
    format: OutputFormatOpt = OutputFormat.TEXT,
) -> None:
    """
    Show cash deposits and cash withdrawals.
    """
    if deposits_only and withdrawals_only:
        raise MutuallyExclusiveOption("--deposits", "--withdrawals")

    if deposits_only:
        total_op = operator.gt
    elif withdrawals_only:
        total_op = operator.lt
    else:
        total_op = None

    filters = create_filters(tax_year=tax_year, total_op=total_op)
    outputter = make_output_generator(parse(files), ctx)
    outputter.show_transfers(format, filters)


@app.command("interest")
def interest_command(
    ctx: typer.Context,
    files: FilesArg,
    tax_year: TaxYearOpt = None,
    format: OutputFormatOpt = OutputFormat.TEXT,
) -> None:
    """
    Show interest earned on cash.
    """
    filters = create_filters(tax_year=tax_year)
    outputter = make_output_generator(parse(files), ctx)
    outputter.show_interest(format, filters)


@app.command("capital-gains")
def capital_gains_command(
    ctx: typer.Context,
    files: FilesArg,
    gains_only: Annotated[
        bool, typer.Option("--gains", help="Show only capital gains.")
    ] = False,
    losses_only: Annotated[
        bool, typer.Option("--losses", help="Show only capital losses.")
    ] = False,
    tax_year: TaxYearOpt = None,
    ticker: TickerOpt = None,
    include_fx_fees: IncludeFxFeesOpt = config.include_fx_fees,
    format: OutputFormatOpt = OutputFormat.TEXT,
    rates_provider: RatesProviderOpt = RatesProvider.YAHOO_FINANCE,
    rates_file: RatesFileOpt = None,
) -> None:
    """
    Show capital gains report.
    """
    if gains_only and losses_only:
        raise MutuallyExclusiveOption("--gains", "--losses")

    if format != OutputFormat.TEXT and tax_year is None:
        raise click.exceptions.UsageError(
            f"The {format.value} format requires the option --tax-year to be used"
        )

    config.include_fx_fees = include_fx_fees

    tax_year = TaxYear(tax_year) if tax_year else None
    ticker = Ticker(ticker) if ticker else None

    try:
        outputter = make_output_generator(parse(files), ctx)
        outputter.show_capital_gains(format, tax_year, ticker, gains_only, losses_only)
    except InvestirError as ex:
        abort(ex)


@app.command("holdings")
def holdings_command(
    ctx: typer.Context,
    files: FilesArg,
    ticker: TickerOpt = None,
    show_gain_loss: Annotated[
        bool, typer.Option("--show-gain-loss", help="Show unrealised gain/loss.")
    ] = False,
    include_fx_fees: IncludeFxFeesOpt = config.include_fx_fees,
    format: OutputFormatOpt = OutputFormat.TEXT,
    rates_provider: RatesProviderOpt = RatesProvider.YAHOO_FINANCE,
    rates_file: RatesFileOpt = None,
) -> None:
    """
    Show current holdings.
    """
    config.include_fx_fees = include_fx_fees

    ticker = Ticker(ticker) if ticker else None

    try:
        outputter = make_output_generator(parse(files), ctx)
        outputter.show_holdings(format, ticker, show_gain_loss)
    except InvestirError as ex:
        abort(ex)


def main() -> None:
    app()
