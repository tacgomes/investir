from prettytable import PrettyTable

from .transaction import Order, Acquisition, Dividend, Transfer, Interest
from .typing import Ticker
from .utils import multiple_filter


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

    def tickers(self) -> list[Ticker]:
        return sorted(set(o.ticker for o in self._orders))

    def show_orders(self, filters=None) -> None:
        table = PrettyTable(
            field_names=(
                "Date",
                "Ticker",
                "Total Cost (£)",
                "Net Proceeds (£)",
                "Quantity",
                "Price (£)",
                "Fees (£)",
            )
        )

        for tr in multiple_filter(filters, self._orders):
            net_proceeds = ""
            total_cost = ""
            if isinstance(tr, Acquisition):
                total_cost = str(round(tr.total_cost, 2))
            else:
                net_proceeds = str(round(tr.net_proceeds, 2))

            table.add_row(
                [
                    tr.date,
                    tr.ticker,
                    total_cost,
                    net_proceeds,
                    tr.quantity,
                    round(tr.price, 2),
                    tr.fees,
                ]
            )

        print(table)

    def show_dividends(self, filters=None):
        table = PrettyTable(
            field_names=("Date", "Ticker", "Amount (£)", "Tax widhheld (£)")
        )

        for tr in multiple_filter(filters, self._dividends):
            if tr.withheld is None:
                withheld = "?"
            else:
                withheld = round(tr.withheld, 2)
            table.add_row([tr.date, tr.ticker, tr.amount, withheld])

        print(table)

    def show_transfers(self, filters=None):
        table = PrettyTable(field_names=("Date", "Amount (£)"))

        for tr in multiple_filter(filters, self._transfers):
            table.add_row([tr.date, tr.amount])

        print(table)

    def show_interest(self, filters=None) -> None:
        table = PrettyTable(field_names=("Date", "Amount (£)"))

        for tr in multiple_filter(filters, self._interest):
            table.add_row([tr.date, tr.amount])

        print(table)

    @staticmethod
    def _insert(l1, l2):
        """Remove duplicates and sort by timestamp."""
        if len(l2) != len(set(l2)):
            raise ValueError("Input file has duplicated entries")

        result = list(set(l1 + l2))
        return sorted(result, key=lambda tr: tr.timestamp)
