from datetime import datetime
from decimal import Decimal

from investir.transaction import (
    Order, OrderType,
    Dividend,
    Transfer, TransferType,
    Interest)
from investir.transactionlog import TransactionLog


ORDER1 = Order(
    datetime(2023, 4, 6, 18, 4, 50),
    'AMZN',
    OrderType.ACQUISITION,
    Decimal(1.0),
    Decimal(2.0),
    Decimal(3.0),
    'ORDER1')

ORDER2 = Order(
    datetime(2024, 2, 5, 14, 7, 20),
    'GOOG',
    OrderType.DISPOSAL,
    Decimal(3.0),
    Decimal(2.0),
    Decimal(1.0),
    'ORDER2')

DIVIDEND1 = Dividend(
    datetime(2023, 2, 5, 14, 7, 20),
    'AMZN',
    Decimal(5.0),
    Decimal(2.0))

DIVIDEND2 = Dividend(
    datetime(2024, 2, 5, 14, 7, 20),
    'GOOG',
    Decimal(5.0),
    Decimal(2.0))

TRANSFER1 = Transfer(
    datetime(2023, 2, 5, 14, 7, 20),
    TransferType.DEPOSIT,
    Decimal(3000.0))

TRANSFER2 = Transfer(
    datetime(2024, 2, 5, 14, 7, 20),
    TransferType.WITHDRAW,
    Decimal(1000.0))

INTEREST1 = Interest(
    datetime(2023, 2, 5, 14, 7, 20),
    Decimal(1000.0))

INTEREST2 = Interest(
    datetime(2024, 2, 5, 14, 7, 20),
    Decimal(500.0))


def test_transactionlog_duplicates_are_removed():
    trlog = TransactionLog()

    trlog.insert_orders([ORDER1, ORDER1])
    trlog.insert_orders([ORDER1])
    assert len(trlog.orders()) == 1

    trlog.insert_dividends([DIVIDEND1, DIVIDEND1])
    trlog.insert_dividends([DIVIDEND1])
    assert len(trlog.dividends()) == 1

    trlog.insert_transfers([TRANSFER1, TRANSFER1])
    trlog.insert_transfers([TRANSFER1])
    assert len(trlog.transfers()) == 1

    trlog.insert_interest([INTEREST1, INTEREST1])
    trlog.insert_interest([INTEREST1])
    assert len(trlog.interest()) == 1


def test_transactionlog_transactions_are_sorted_by_timestamp():
    trlog = TransactionLog()
    trlog.insert_orders([ORDER2, ORDER1])

    orders = trlog.orders()
    assert len(orders) == 2
    assert orders[0].ticker == ORDER1.ticker
    assert orders[1].ticker == ORDER2.ticker


def test_transactionlog_dividends_are_sorted_by_timestamp():
    trlog = TransactionLog()
    trlog.insert_dividends([DIVIDEND2, DIVIDEND1])

    dividends = trlog.dividends()
    assert len(dividends) == 2
    assert dividends[0].ticker == DIVIDEND1.ticker
    assert dividends[1].ticker == DIVIDEND2.ticker


def test_transactionlog_transfers_are_sorted_by_timestamp():
    trlog = TransactionLog()
    trlog.insert_transfers([TRANSFER2, TRANSFER1])

    transfers = trlog.transfers()
    assert len(transfers) == 2
    assert transfers[0].type == TransferType.DEPOSIT
    assert transfers[1].type == TransferType.WITHDRAW


def test_transactionlog_interest_is_sorted_by_timestamp():
    trlog = TransactionLog()
    trlog.insert_interest([INTEREST2, INTEREST1])

    interest = trlog.interest()
    assert len(interest) == 2
    assert interest[0].amount == INTEREST1.amount
    assert interest[1].amount == INTEREST2.amount


def test_transactionlog_show_orders(capsys):
    trlog = TransactionLog()
    trlog.insert_orders([ORDER1, ORDER2])
    trlog.show_orders()
    captured = capsys.readouterr()
    assert ORDER1.ticker in captured.out
    assert ORDER2.ticker in captured.out


def test_transactionlog_show_dividends(capsys):
    trlog = TransactionLog()
    trlog.insert_dividends([DIVIDEND1, DIVIDEND2])
    trlog.show_dividends()
    captured = capsys.readouterr()
    assert DIVIDEND1.ticker in captured.out
    assert DIVIDEND2.ticker in captured.out


def test_transactionlog_show_transfers(capsys):
    trlog = TransactionLog()
    trlog.insert_transfers([TRANSFER1, TRANSFER2])
    trlog.show_transfers()
    captured = capsys.readouterr()
    assert str(TRANSFER1.amount) in captured.out
    assert str(TRANSFER2.amount) in captured.out


def test_transactionlog_show_interest(capsys):
    trlog = TransactionLog()
    trlog.insert_interest([INTEREST1, INTEREST2])
    trlog.show_interest()
    captured = capsys.readouterr()
    assert str(INTEREST1.amount) in captured.out
    assert str(INTEREST2.amount) in captured.out
