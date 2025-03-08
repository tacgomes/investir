import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import TypeVar

from investir.config import config
from investir.const import BASE_CURRENCY
from investir.exceptions import AmbiguousTickerError
from investir.prettytable import Field, Format, OutputFormat, PrettyTable
from investir.taxcalculator import TaxCalculator
from investir.transaction import (
    Acquisition,
    Disposal,
    Transaction,
)
from investir.trhistory import TransactionHistory
from investir.typing import TaxYear, Ticker
from investir.utils import boldify, multifilter, tax_year_full_date, tax_year_short_date

T = TypeVar("T", bound=Transaction)

logger = logging.getLogger(__name__)


def gbp(amount: Decimal) -> str:
    sign = "" if amount >= 0.0 else "-"
    return f"{sign}£{abs(amount):.2f}"


@dataclass
class CapitalGainsSummary:
    num_disposals: int
    disposal_proceeds: Decimal
    total_cost: Decimal
    total_gains: Decimal
    total_losses: Decimal

    @property
    def net_gains(self) -> Decimal:
        return self.total_gains - self.total_losses

    def __str__(self) -> str:
        return (
            f"{'Number of disposals:':40}{self.num_disposals:>10}      "
            f"{'Gains in the year, before losses:':34}{gbp(self.total_gains):>10}\n"
            f"{'Disposal proceeds:':40}{gbp(self.disposal_proceeds):>10}      "
            f"{'Losses in the year:':34}{gbp(self.total_losses):>10}\n"
            f"{'Allowable costs (incl. purchase price):':40}"
            f"{gbp(self.total_cost):>10}      "
            f"{'Net gain or loss:':34}{gbp(self.net_gains):>10}\n"
        )


class OutputGenerator:
    def __init__(self, trhistory: TransactionHistory, taxcalc: TaxCalculator) -> None:
        self._trhistory = trhistory
        self._taxcalc = taxcalc

    def show_orders(
        self, format: OutputFormat, filters: Sequence[Callable] | None = None
    ) -> None:
        if table := self._create_orders_table(filters):
            print(table.to_string(format, leading_nl=config.logging_enabled))

    def show_dividends(
        self, format: OutputFormat, filters: Sequence[Callable] | None = None
    ) -> None:
        if table := self._create_dividends_table(filters):
            print(table.to_string(format, leading_nl=config.logging_enabled))

    def show_transfers(
        self, format: OutputFormat, filters: Sequence[Callable] | None = None
    ) -> None:
        if table := self._create_transfers_table(filters):
            print(table.to_string(format, leading_nl=config.logging_enabled))

    def show_interest(
        self, format: OutputFormat, filters: Sequence[Callable] | None = None
    ) -> None:
        if table := self._create_interest_table(filters):
            print(table.to_string(format, leading_nl=config.logging_enabled))

    def show_capital_gains(
        self,
        format: OutputFormat,
        tax_year_filter: TaxYear | None,
        ticker_filter: Ticker | None,
        gains_only: bool,
        losses_only: bool,
    ) -> None:
        if tax_year_filter is not None:
            tax_years: Sequence = [tax_year_filter]
        else:
            tax_years = sorted(self._taxcalc.disposal_years())

        for tax_year_idx, tax_year in enumerate(tax_years):
            table, summary = self._create_capital_gains_table_and_summary(
                tax_year, ticker_filter, gains_only, losses_only
            )

            if table:
                print(end="\n" if tax_year_idx == 0 and config.logging_enabled else "")

                if format == OutputFormat.TEXT:
                    print(
                        boldify(
                            f"Capital Gains Tax Report {tax_year_short_date(tax_year)}"
                        )
                    )
                    print(tax_year_full_date(tax_year))
                    print(table.to_string(format))
                    print(summary)
                else:
                    print(table.to_string(format, leading_nl=False))

    def show_holdings(
        self,
        format: OutputFormat,
        ticker_filter: Ticker | None = None,
        show_gain_loss: bool = False,
    ) -> None:
        if table := self._create_holdings_table(ticker_filter, show_gain_loss):
            print(table.to_string(format, leading_nl=config.logging_enabled))

    def _create_orders_table(
        self, filters: Sequence[Callable] | None = None
    ) -> PrettyTable:
        table = PrettyTable(
            [
                Field("Date", Format.DATE),
                Field("Security Name"),
                Field("ISIN"),
                Field("Ticker"),
                Field("Cost", Format.MONEY, show_sum=True),
                Field("Proceeds", Format.MONEY, show_sum=True),
                Field("Quantity", Format.QUANTITY),
                Field("Price", Format.MONEY),
                Field("Fees", Format.MONEY, show_sum=True),
            ]
        )

        transactions = list(multifilter(filters, self._trhistory.orders))
        last_idx = len(transactions) - 1

        for idx, tr in enumerate(transactions):
            cost = tr.total if isinstance(tr, Acquisition) else None
            proceeds = tr.total if isinstance(tr, Disposal) else None

            divider = (
                idx == last_idx or tr.tax_year() != transactions[idx + 1].tax_year()
            )

            table.add_row(
                [
                    tr.date,
                    tr.name,
                    tr.isin,
                    tr.ticker,
                    cost,
                    proceeds,
                    tr.quantity,
                    tr.price,
                    tr.fees.total,
                ],
                divider=divider,
            )

        return table

    def _create_dividends_table(
        self, filters: Sequence[Callable] | None = None
    ) -> PrettyTable:
        table = PrettyTable(
            [
                Field("Date", Format.DATE),
                Field("Security Name"),
                Field("ISIN"),
                Field("Ticker"),
                Field("Net Amount", Format.MONEY, show_sum=True),
                Field("Widthheld Amount", Format.MONEY, show_sum=True),
            ]
        )

        transactions = list(multifilter(filters, self._trhistory.dividends))
        last_idx = len(transactions) - 1

        for idx, tr in enumerate(transactions):
            divider = (
                idx == last_idx or tr.tax_year() != transactions[idx + 1].tax_year()
            )

            table.add_row(
                [
                    tr.date,
                    tr.name,
                    tr.isin,
                    tr.ticker,
                    tr.total,
                    tr.withheld,
                ],
                divider=divider,
            )

        return table

    def _create_transfers_table(
        self, filters: Sequence[Callable] | None = None
    ) -> PrettyTable:
        table = PrettyTable(
            [
                Field("Date", Format.DATE),
                Field("Deposit", Format.MONEY, show_sum=True),
                Field("Withdrawal", Format.MONEY, show_sum=True),
            ]
        )

        transactions = list(multifilter(filters, self._trhistory.transfers))
        last_idx = len(transactions) - 1

        for idx, tr in enumerate(transactions):
            if tr.total.amount > 0:
                deposited = tr.total
                widthdrew = ""
            else:
                deposited = ""
                widthdrew = abs(tr.total)

            divider = (
                idx == last_idx or tr.tax_year() != transactions[idx + 1].tax_year()
            )

            table.add_row([tr.date, deposited, widthdrew], divider=divider)

        return table

    def _create_interest_table(
        self, filters: Sequence[Callable] | None = None
    ) -> PrettyTable:
        table = PrettyTable(
            [
                Field("Date", Format.DATE),
                Field("Amount", Format.MONEY, show_sum=True),
            ]
        )

        transactions = list(multifilter(filters, self._trhistory.interest))
        last_idx = len(transactions) - 1

        for idx, tr in enumerate(transactions):
            divider = (
                idx == last_idx or tr.tax_year() != transactions[idx + 1].tax_year()
            )

            table.add_row([tr.date, tr.total], divider=divider)

        return table

    def _create_capital_gains_table_and_summary(
        self,
        tax_year: TaxYear,
        ticker_filter: Ticker | None,
        gains_only: bool,
        losses_only: bool,
    ) -> tuple[PrettyTable, CapitalGainsSummary]:
        assert not (gains_only and losses_only)

        table = PrettyTable(
            [
                Field("Disposal Date", Format.DATE),
                Field("Identification"),
                Field("Security Name"),
                Field("ISIN"),
                Field("Quantity", Format.QUANTITY),
                Field(f"Cost ({BASE_CURRENCY})", Format.DECIMAL),
                Field(f"Proceeds ({BASE_CURRENCY})", Format.DECIMAL),
                Field(f"Gain/loss ({BASE_CURRENCY})", Format.DECIMAL),
            ]
        )

        num_disposals = 0
        disposal_proceeds = total_cost = total_gains = total_losses = Decimal("0.0")

        for cg in self._taxcalc.capital_gains(tax_year):
            if ticker_filter is not None and cg.disposal.ticker != ticker_filter:
                continue

            if gains_only and cg.gain_loss < 0.0:
                continue

            if losses_only and cg.gain_loss > 0.0:
                continue

            table.add_row(
                [
                    cg.disposal.date,
                    cg.identification,
                    cg.disposal.name,
                    cg.disposal.isin,
                    cg.quantity,
                    cg.cost,
                    cg.disposal.gross_proceeds.amount,
                    cg.gain_loss,
                ]
            )

            num_disposals += 1
            disposal_proceeds += round(cg.disposal.gross_proceeds.amount, 2)
            total_cost += round(cg.cost, 2)
            if cg.gain_loss > 0.0:
                total_gains += cg.gain_loss
            else:
                total_losses += abs(cg.gain_loss)

        summary = CapitalGainsSummary(
            num_disposals, disposal_proceeds, total_cost, total_gains, total_losses
        )

        return table, summary

    def _create_holdings_table(
        self, ticker_filter: Ticker | None = None, show_gain_loss: bool = False
    ) -> PrettyTable:
        table = PrettyTable(
            [
                Field("Security Name"),
                Field("ISIN"),
                Field(f"Cost ({BASE_CURRENCY})", Format.DECIMAL),
                Field("Quantity", Format.QUANTITY),
                Field(
                    f"Current Value ({BASE_CURRENCY})",
                    Format.DECIMAL,
                    visible=show_gain_loss,
                ),
                Field(
                    f"Gain/Loss ({BASE_CURRENCY})",
                    Format.DECIMAL,
                    visible=show_gain_loss,
                ),
                Field("Weight (%)", Format.DECIMAL, visible=show_gain_loss),
            ]
        )

        holdings = self._taxcalc.holdings

        if ticker_filter is not None:
            try:
                isin = self._trhistory.get_ticker_isin(ticker_filter)
            except AmbiguousTickerError as e:
                logger.warning(e)
                holdings = []
            else:
                if holding := next((h for h in holdings if h.isin == isin), None):
                    holdings = [holding]
                else:
                    holdings = []

        holdings = sorted(holdings, key=lambda h: h.cost, reverse=True)

        if show_gain_loss:
            values = {
                holding.isin: value
                for holding in holdings
                if (value := self._taxcalc.get_holding_value(holding.isin)) is not None
            }
        else:
            values = {}

        portfolio_value = sum(val for val in values.values())
        last_idx = len(holdings) - 1

        for idx, holding in enumerate(holdings):
            gain_loss: Decimal | None = None
            weight: Decimal | None = None

            if value := values.get(holding.isin):
                gain_loss = value - holding.cost
                weight = value / portfolio_value * 100

            table.add_row(
                [
                    self._trhistory.get_security_name(holding.isin),
                    holding.isin,
                    holding.cost,
                    holding.quantity,
                    value,
                    gain_loss or "n/a",
                    weight or "n/a",
                ],
                divider=idx == last_idx,
            )

        return table
