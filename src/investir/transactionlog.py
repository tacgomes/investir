from prettytable import PrettyTable

from .transaction import Transaction, TransactionType


class TransactionLog:
    def __init__(self) -> None:
        self._transactions: list[Transaction] = []

    def add(self, transactions: list[Transaction]) -> None:
        self._transactions.extend(transactions)

    def show(self) -> None:
        table = PrettyTable()
        table.field_names = (
            'Date', 'Ticker', 'Disposal', 'Price', 'Quantity', 'Fees')

        for tr in self._transactions:
            tr_type = 'Yes' if tr.type == TransactionType.DISPOSAL else ' '
            table.add_row([
                tr.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                tr.ticker,
                tr_type,
                tr.price,
                tr.quantity,
                tr.fees])

        print(table)
