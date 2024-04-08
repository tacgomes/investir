from prettytable import PrettyTable

from .transaction import (
    Order, OrderType,
    Dividend,
    Transfer, TransferType,
    Interest)
from .utils import multiple_filter


class TransactionLog:
    def __init__(self) -> None:
        self._orders: list[Order] = []
        self._dividends: list[Dividend] = []
        self._transfers: list[Transfer] = []
        self._interest: list[Interest] = []

    def insert_orders(self, orders: list[Order]) -> None:
        self._orders = TransactionLog._insert(self._orders, orders)

    def insert_dividends(self, dividends: list[Dividend]) -> None:
        self._dividends = TransactionLog._insert(self._dividends, dividends)

    def insert_transfers(self, transfers: list[Transfer]) -> None:
        self._transfers = TransactionLog._insert(self._transfers, transfers)

    def insert_interest(self, interest: list[Interest]) -> None:
        self._interest = TransactionLog._insert(self._interest, interest)

    def orders(self) -> list[Order]:
        return self._orders[:]

    def dividends(self) -> list[Dividend]:
        return self._dividends[:]

    def transfers(self) -> list[Transfer]:
        return self._transfers[:]

    def interest(self) -> list[Interest]:
        return self._interest[:]

    def show_orders(self, filters=None) -> None:
        table = PrettyTable(
            field_names=(
                'Date', 'Ticker', 'Disposal', 'Price',
                'Quantity', 'Fees', 'Total', 'Order ID'))

        for tr in multiple_filter(filters, self._orders):
            type_str = 'Yes' if tr.type == OrderType.DISPOSAL else ' '

            table.add_row([
                tr.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                tr.ticker,
                type_str,
                tr.price,
                tr.quantity,
                tr.fees,
                round(tr.total_amount(), 2),
                tr.order_id])

        print(table)

    def show_dividends(self, filters=None):
        table = PrettyTable(
            field_names=('Date', 'Ticker', 'Amount', 'Tax widhheld'))

        for tr in multiple_filter(filters, self._dividends):
            table.add_row([
                tr.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                tr.ticker,
                tr.amount,
                round(tr.withheld, 2)])

        print(table)

    def show_transfers(self, filters=None):
        table = PrettyTable(
            field_names=('Date', 'Withdraw', 'Amount'))

        for tr in multiple_filter(filters, self._transfers):
            type_str = 'Yes' if tr.type == TransferType.WITHDRAW else ' '

            table.add_row([
                tr.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                type_str,
                tr.amount])

        print(table)

    def show_interest(self, filters=None) -> None:
        table = PrettyTable(
            field_names=('Date', 'Amount'))

        for tr in multiple_filter(filters,  self._interest):
            table.add_row([
                tr.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                tr.amount])

        print(table)

    @staticmethod
    def _insert(l1, l2):
        """ Remove duplicates and sort by timestamp. """
        # FIXME: this is not very efficient but it will do for now.
        result = list(set(l1 + l2))
        return sorted(result, key=lambda tr: tr.timestamp)
