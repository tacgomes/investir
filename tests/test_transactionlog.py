from datetime import datetime
from decimal import Decimal

from investir.transaction import Transaction, TransactionType
from investir.transactionlog import TransactionLog

EXPECTED_OUTPUT = '''\
+---------------------+--------+----------+-------+----------+------+
|         Date        | Ticker | Disposal | Price | Quantity | Fees |
+---------------------+--------+----------+-------+----------+------+
| 2023-04-06 18:04:50 |  AMZN  |          |   1   |    2     |  3   |
| 2024-02-05 14:07:20 |  GOOG  |   Yes    |   3   |    2     |  1   |
+---------------------+--------+----------+-------+----------+------+
'''


def test_transactionlog_show(capsys):
    trlog = TransactionLog()
    trlog.add([
        Transaction(
            datetime(2023, 4, 6, 18, 4, 50),
            'AMZN',
            TransactionType.ACQUISITION,
            Decimal(1.0),
            Decimal(2.0),
            Decimal(3.0)),
        Transaction(
            datetime(2024, 2, 5, 14, 7, 20),
            'GOOG',
            TransactionType.DISPOSAL,
            Decimal(3.0),
            Decimal(2.0),
            Decimal(1.0))
        ])

    trlog.show()

    captured = capsys.readouterr()

    assert captured.out == EXPECTED_OUTPUT
