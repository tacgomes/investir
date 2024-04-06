from prettytable import PrettyTable

from .transaction import Transaction, TransactionType


class TransactionLog:
    def __init__(self) -> None:
        self._transactions: list[Transaction] = []

    def insert(self, transactions: list[Transaction]) -> None:
        self._transactions.extend(transactions)

        # Remove duplicates and sort by timestamp. This is not very
        # efficient but it will do for now.
        self._transactions = sorted(
            list(set(self._transactions)), key=lambda tr: tr.timestamp)

    def to_list(self) -> list[Transaction]:
        return self._transactions[:]

    def show(self) -> None:
        table = PrettyTable(
            field_names=(
                'Date', 'Ticker', 'Disposal', 'Price',
                'Quantity', 'Fees', 'Total', 'Order ID'))

        for tr in self._transactions:
            tr_type = 'Yes' if tr.type == TransactionType.DISPOSAL else ' '
            table.add_row([
                tr.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                tr.ticker,
                tr_type,
                tr.price,
                tr.quantity,
                tr.fees,
                round(tr.total_amount(), 2),
                tr.order_id])

        print(table)
