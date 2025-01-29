from collections.abc import Callable, Mapping, Sequence, ValuesView
from typing import NamedTuple, TypeVar

from investir.exceptions import AmbiguousTickerError
from investir.prettytable import Field, Format, PrettyTable
from investir.transaction import (
    Acquisition,
    Dividend,
    Interest,
    Order,
    Transaction,
    Transfer,
)
from investir.typing import ISIN, Ticker
from investir.utils import multifilter

T = TypeVar("T", bound=Transaction)


def unique_and_sorted(transactions: Sequence[T] | None) -> Sequence[T]:
    """Remove duplicated transactions and sort them by timestamp."""
    return sorted(set(transactions or []), key=lambda tr: tr.timestamp)


class Security(NamedTuple):
    isin: ISIN
    name: str = ""


class TrHistory:
    def __init__(
        self,
        *,
        orders: Sequence[Order] | None = None,
        dividends: Sequence[Dividend] | None = None,
        transfers: Sequence[Transfer] | None = None,
        interest: Sequence[Interest] | None = None,
    ) -> None:
        self._orders = unique_and_sorted(orders)
        self._dividends = unique_and_sorted(dividends)
        self._transfers = unique_and_sorted(transfers)
        self._interest = unique_and_sorted(interest)
        self._securities: Mapping[ISIN, Security] = {}

    @property
    def orders(self) -> Sequence[Order]:
        return self._orders

    @property
    def dividends(self) -> Sequence[Dividend]:
        return self._dividends

    @property
    def transfers(self) -> Sequence[Transfer]:
        return self._transfers

    @property
    def interest(self) -> Sequence[Interest]:
        return self._interest

    @property
    def securities(self) -> ValuesView[Security]:
        return self._securities_map().values()

    def get_security_name(self, isin: ISIN) -> str | None:
        security = self._securities_map().get(isin)
        return security.name if security else None

    def get_ticker_isin(self, ticker: Ticker) -> ISIN | None:
        isins = set(o.isin for o in self._orders if o.ticker == ticker)

        match len(isins):
            case 0:
                return None
            case 1:
                return next(iter(isins))
            case _:
                raise AmbiguousTickerError(ticker)

    def get_orders_table(
        self, filters: Sequence[Callable] | None = None
    ) -> PrettyTable:
        table = PrettyTable(
            [
                Field("Date", Format.DATE),
                Field("Security Name"),
                Field("ISIN"),
                Field("Ticker"),
                Field("Total Cost", Format.MONEY, show_sum=True),
                Field("Net Proceeds", Format.MONEY, show_sum=True),
                Field("Quantity", Format.QUANTITY),
                Field("Price", Format.MONEY),
                Field("Fees", Format.MONEY, show_sum=True),
            ]
        )

        transactions = list(multifilter(filters, self._orders))
        last_idx = len(transactions) - 1

        for idx, tr in enumerate(transactions):
            net_proceeds = None
            total_cost = None
            if isinstance(tr, Acquisition):
                total_cost = tr.total_cost
            else:
                net_proceeds = tr.net_proceeds

            divider = (
                idx == last_idx or tr.tax_year() != transactions[idx + 1].tax_year()
            )

            table.add_row(
                [
                    tr.date,
                    tr.name,
                    tr.isin,
                    tr.ticker,
                    total_cost,
                    net_proceeds,
                    tr.quantity,
                    tr.price,
                    tr.fees,
                ],
                divider=divider,
            )

        return table

    def get_dividends_table(
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

        transactions = list(multifilter(filters, self._dividends))
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

    def get_transfers_table(
        self, filters: Sequence[Callable] | None = None
    ) -> PrettyTable:
        table = PrettyTable(
            [
                Field("Date", Format.DATE),
                Field("Deposit", Format.MONEY, show_sum=True),
                Field("Withdrawal", Format.MONEY, show_sum=True),
            ]
        )

        transactions = list(multifilter(filters, self._transfers))
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

    def get_interest_table(
        self, filters: Sequence[Callable] | None = None
    ) -> PrettyTable:
        table = PrettyTable(
            [
                Field("Date", Format.DATE),
                Field("Amount", Format.MONEY, show_sum=True),
            ]
        )

        transactions = list(multifilter(filters, self._interest))
        last_idx = len(transactions) - 1

        for idx, tr in enumerate(transactions):
            divider = (
                idx == last_idx or tr.tax_year() != transactions[idx + 1].tax_year()
            )

            table.add_row([tr.date, tr.total], divider=divider)

        return table

    def _securities_map(self) -> Mapping[ISIN, Security]:
        if not self._securities:
            self._securities = {
                o.isin: Security(o.isin, o.name)
                for o in sorted(self._orders, key=lambda o: o.name)
            }
        return self._securities
