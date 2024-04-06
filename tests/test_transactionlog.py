from datetime import datetime
from decimal import Decimal

from investir.transaction import Transaction, TransactionType
from investir.transactionlog import TransactionLog

EXPECTED_OUTPUT = '''\
+---------------------+--------+----------+-------+----------+------+-------+----------+
|         Date        | Ticker | Disposal | Price | Quantity | Fees | Total | Order ID |
+---------------------+--------+----------+-------+----------+------+-------+----------+
| 2023-04-06 18:04:50 |  AMZN  |          |   1   |    2     |  3   |  5.00 |  ORDER1  |
| 2024-02-05 14:07:20 |  GOOG  |   Yes    |   3   |    2     |  1   |  5.00 |  ORDER2  |
+---------------------+--------+----------+-------+----------+------+-------+----------+
'''

TR1 = Transaction(
    datetime(2023, 4, 6, 18, 4, 50),
    'AMZN',
    TransactionType.ACQUISITION,
    Decimal(1.0),
    Decimal(2.0),
    Decimal(3.0),
    'ORDER1')

TR2 = Transaction(
    datetime(2024, 2, 5, 14, 7, 20),
    'GOOG',
    TransactionType.DISPOSAL,
    Decimal(3.0),
    Decimal(2.0),
    Decimal(1.0),
    'ORDER2')


def test_transactionlog_duplicates_are_removed():
    trlog = TransactionLog()
    trlog.insert([TR1, TR1])
    trlog.insert([TR1])
    assert len(trlog.to_list()) == 1


def test_transactionlog_entries_are_sorted_by_date():
    trlog = TransactionLog()
    trlog.insert([TR2, TR1])
    transactions = trlog.to_list()
    assert len(transactions) == 2
    assert transactions[0].ticker == 'AMZN'
    assert transactions[1].ticker == 'GOOG'


def test_transactionlog_show(capsys):
    trlog = TransactionLog()
    trlog.insert([TR1, TR2])
    trlog.show()
    captured = capsys.readouterr()
    assert captured.out == EXPECTED_OUTPUT
