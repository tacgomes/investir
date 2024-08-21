from decimal import Decimal
from typing import NamedTuple

import prettytable

from .transaction import Order, Acquisition, Dividend, Transfer, Interest
from .typing import ISIN, Ticker
from .utils import multiple_filter


class Security(NamedTuple):
    isin: ISIN
    name: str = ""


class TrHistory:
    def __init__(self) -> None:
        self._orders: list[Order] = []
        self._dividends: list[Dividend] = []
        self._transfers: list[Transfer] = []
        self._interest: list[Interest] = []

    def insert_orders(self, orders: list[Order]) -> None:
        self._orders = TrHistory._insert(self._orders, orders)

    def insert_dividends(self, dividends: list[Dividend]) -> None:
        self._dividends = TrHistory._insert(self._dividends, dividends)

    def insert_transfers(self, transfers: list[Transfer]) -> None:
        self._transfers = TrHistory._insert(self._transfers, transfers)

    def insert_interest(self, interest: list[Interest]) -> None:
        self._interest = TrHistory._insert(self._interest, interest)

    def orders(self) -> list[Order]:
        return self._orders[:]

    def dividends(self) -> list[Dividend]:
        return self._dividends[:]

    def transfers(self) -> list[Transfer]:
        return self._transfers[:]

    def interest(self) -> list[Interest]:
        return self._interest[:]

    def securities(self) -> list[Security]:
        securities = {o.isin: o.name for o in self._orders}
        return sorted(
            (Security(isin, name) for isin, name in securities.items()),
            key=lambda t: t.name,
        )

    def get_security_name(self, isin: ISIN) -> str | None:
        securities = {o.isin: o.name for o in self._orders}
        return securities.get(isin)

    def get_ticker_isin(self, ticker: Ticker) -> ISIN | None:
        isins = set(o.isin for o in self._orders if o.ticker == ticker)

        if not len(isins) == 1:
            return None

        return next(iter(isins))

    def show_orders(self, filters=None) -> None:
        table = prettytable.PrettyTable(
            field_names=(
                "Date",
                "ISIN",
                "Security",
                "Ticker",
                "Total Cost (£)",
                "Net Proceeds (£)",
                "Quantity",
                "Price (£)",
                "Fees (£)",
            )
        )
        table.vrules = prettytable.NONE

        transactions = list(multiple_filter(filters, self._orders))
        last_idx = len(transactions) - 1
        total_total_cost = total_net_proceeds = total_fees = Decimal("0.0")

        for idx, tr in enumerate(transactions):
            net_proceeds = ""
            total_cost = ""
            if isinstance(tr, Acquisition):
                total_cost = f"{tr.total_cost:.2f}"
                total_total_cost += round(tr.total_cost, 2)
            else:
                net_proceeds = f"{tr.net_proceeds:.2f}"
                total_net_proceeds += round(tr.net_proceeds, 2)

            divider = (
                idx == last_idx or tr.tax_year() != transactions[idx + 1].tax_year()
            )

            table.add_row(
                [
                    tr.date,
                    tr.isin,
                    tr.name,
                    tr.ticker,
                    total_cost,
                    net_proceeds,
                    tr.quantity,
                    f"{tr.price:.2f}",
                    tr.fees,
                ],
                divider=divider,
            )

            total_fees += tr.fees

        table.add_row(
            [
                "",
                "",
                "",
                "",
                total_total_cost,
                total_net_proceeds,
                "",
                "",
                total_fees,
            ]
        )

        print(table, "\n")

    def show_dividends(self, filters=None):
        table = prettytable.PrettyTable(
            field_names=(
                "Date",
                "ISIN",
                "Security",
                "Ticker",
                "Amount (£)",
                "Tax widhheld (£)",
            )
        )
        table.vrules = prettytable.NONE

        transactions = list(multiple_filter(filters, self._dividends))
        last_idx = len(transactions) - 1
        total_paid = total_withheld = Decimal("0.0")

        for idx, tr in enumerate(transactions):
            if tr.withheld is None:
                withheld = "?"
            else:
                withheld = f"{tr.withheld:.2f}"
                total_withheld += round(tr.withheld, 2)

            divider = (
                idx == last_idx or tr.tax_year() != transactions[idx + 1].tax_year()
            )

            table.add_row(
                [tr.date, tr.isin, tr.name, tr.ticker, tr.amount, withheld],
                divider=divider,
            )

            total_paid += tr.amount

        table.add_row(["", "", "", "", total_paid, total_withheld])

        print(table, "\n")

    def show_transfers(self, filters=None):
        table = prettytable.PrettyTable(
            field_names=("Date", "Deposited (£)", "Withdrew (£)")
        )
        table.vrules = prettytable.NONE

        transactions = list(multiple_filter(filters, self._transfers))
        last_idx = len(transactions) - 1
        total_deposited = total_withdrew = Decimal("0.0")

        for idx, tr in enumerate(transactions):
            if tr.amount > 0:
                deposited = tr.amount
                widthdrew = ""
                total_deposited += tr.amount
            else:
                deposited = ""
                widthdrew = abs(tr.amount)
                total_withdrew += abs(tr.amount)

            divider = (
                idx == last_idx or tr.tax_year() != transactions[idx + 1].tax_year()
            )

            table.add_row([tr.date, deposited, widthdrew], divider=divider)

        table.add_row(["", total_deposited, total_withdrew])

        print(table, "\n")

    def show_interest(self, filters=None) -> None:
        table = prettytable.PrettyTable(field_names=("Date", "Amount (£)"))
        table.vrules = prettytable.NONE

        transactions = list(multiple_filter(filters, self._interest))
        last_idx = len(transactions) - 1
        total_interest = Decimal("0.0")

        for idx, tr in enumerate(transactions):
            divider = (
                idx == last_idx or tr.tax_year() != transactions[idx + 1].tax_year()
            )

            table.add_row([tr.date, tr.amount], divider=divider)

            total_interest += tr.amount

        table.add_row(["", total_interest])

        print(table, "\n")

    @staticmethod
    def _insert(l1, l2):
        """Remove duplicates and sort by timestamp."""
        if len(l2) != len(set(l2)):
            raise ValueError("Input file has duplicated entries")

        result = list(set(l1 + l2))
        return sorted(result, key=lambda tr: tr.timestamp)
