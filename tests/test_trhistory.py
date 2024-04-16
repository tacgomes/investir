from datetime import datetime
from decimal import Decimal

from investir.transaction import (
    Acquisition, Disposal, Dividend, Transfer, Interest)
from investir.trhistory import TrHistory


ORDER1 = Acquisition(
    datetime(2023, 4, 6, 18, 4, 50),
    ticker='AMZN',
    amount=Decimal(10.0),
    quantity=Decimal(1.0),
    fees=Decimal(0.5),
    order_id='ORDER1')

ORDER2 = Disposal(
    datetime(2024, 2, 5, 14, 7, 20),
    ticker='GOOG',
    amount=Decimal(15.0),
    quantity=Decimal(2.0),
    fees=Decimal(1.0),
    order_id='ORDER2')

DIVIDEND1 = Dividend(
    datetime(2023, 2, 5, 14, 7, 20),
    ticker='AMZN',
    amount=Decimal(5.0),
    withheld=Decimal(2.0))

DIVIDEND2 = Dividend(
    datetime(2024, 2, 5, 14, 7, 20),
    ticker='GOOG',
    amount=Decimal(5.0),
    withheld=Decimal(2.0))

TRANSFER1 = Transfer(
    datetime(2023, 2, 5, 14, 7, 20),
    Decimal(3000.0))

TRANSFER2 = Transfer(
    datetime(2024, 2, 5, 14, 7, 20),
    Decimal(-1000.0))

INTEREST1 = Interest(
    datetime(2023, 2, 5, 14, 7, 20),
    Decimal(1000.0))

INTEREST2 = Interest(
    datetime(2024, 2, 5, 14, 7, 20),
    Decimal(500.0))


def test_trhistory_duplicates_are_removed():
    tr_hist = TrHistory()

    tr_hist.insert_orders([ORDER1, ORDER1])
    tr_hist.insert_orders([ORDER1])
    assert len(tr_hist.orders()) == 1

    tr_hist.insert_dividends([DIVIDEND1, DIVIDEND1])
    tr_hist.insert_dividends([DIVIDEND1])
    assert len(tr_hist.dividends()) == 1

    tr_hist.insert_transfers([TRANSFER1, TRANSFER1])
    tr_hist.insert_transfers([TRANSFER1])
    assert len(tr_hist.transfers()) == 1

    tr_hist.insert_interest([INTEREST1, INTEREST1])
    tr_hist.insert_interest([INTEREST1])
    assert len(tr_hist.interest()) == 1


def test_trhistory_transactions_are_sorted_by_timestamp():
    tr_hist = TrHistory()
    tr_hist.insert_orders([ORDER2, ORDER1])

    orders = tr_hist.orders()
    assert len(orders) == 2
    assert orders[0].ticker == ORDER1.ticker
    assert orders[1].ticker == ORDER2.ticker


def test_trhistory_dividends_are_sorted_by_timestamp():
    tr_hist = TrHistory()
    tr_hist.insert_dividends([DIVIDEND2, DIVIDEND1])

    dividends = tr_hist.dividends()
    assert len(dividends) == 2
    assert dividends[0].ticker == DIVIDEND1.ticker
    assert dividends[1].ticker == DIVIDEND2.ticker


def test_trhistory_transfers_are_sorted_by_timestamp():
    tr_hist = TrHistory()
    tr_hist.insert_transfers([TRANSFER2, TRANSFER1])

    transfers = tr_hist.transfers()
    assert len(transfers) == 2
    assert transfers[0].amount == Decimal('3000')
    assert transfers[1].amount == Decimal('-1000')


def test_trhistory_interest_is_sorted_by_timestamp():
    tr_hist = TrHistory()
    tr_hist.insert_interest([INTEREST2, INTEREST1])

    interest = tr_hist.interest()
    assert len(interest) == 2
    assert interest[0].amount == INTEREST1.amount
    assert interest[1].amount == INTEREST2.amount


def test_trhistory_show_orders(capsys):
    tr_hist = TrHistory()
    tr_hist.insert_orders([ORDER1, ORDER2])
    tr_hist.show_orders()
    captured = capsys.readouterr()
    assert ORDER1.ticker in captured.out
    assert ORDER2.ticker in captured.out


def test_trhistory_show_dividends(capsys):
    tr_hist = TrHistory()
    tr_hist.insert_dividends([DIVIDEND1, DIVIDEND2])
    tr_hist.show_dividends()
    captured = capsys.readouterr()
    assert DIVIDEND1.ticker in captured.out
    assert DIVIDEND2.ticker in captured.out


def test_trhistory_show_transfers(capsys):
    tr_hist = TrHistory()
    tr_hist.insert_transfers([TRANSFER1, TRANSFER2])
    tr_hist.show_transfers()
    captured = capsys.readouterr()
    assert str(TRANSFER1.amount) in captured.out
    assert str(TRANSFER2.amount) in captured.out


def test_trhistory_show_interest(capsys):
    tr_hist = TrHistory()
    tr_hist.insert_interest([INTEREST1, INTEREST2])
    tr_hist.show_interest()
    captured = capsys.readouterr()
    assert str(INTEREST1.amount) in captured.out
    assert str(INTEREST2.amount) in captured.out
