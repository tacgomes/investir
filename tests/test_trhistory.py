from dataclasses import replace
from datetime import datetime
from decimal import Decimal

import pytest

from investir.exceptions import AmbiguousTickerError
from investir.transaction import Acquisition, Disposal, Dividend, Interest, Transfer
from investir.trhistory import TrHistory
from investir.typing import ISIN, Ticker

ORDER1 = Acquisition(
    datetime(2023, 4, 6, 18, 4, 50),
    isin=ISIN("AMZN-ISIN"),
    ticker=Ticker("AMZN"),
    name="Amazon",
    amount=Decimal("10.0"),
    quantity=Decimal("1.0"),
    fees=Decimal("0.5"),
    tr_id="ORDER1",
)

ORDER2 = Disposal(
    datetime(2024, 2, 5, 14, 7, 20),
    isin=ISIN("GOOG-ISIN"),
    ticker=Ticker("GOOG"),
    name="Alphabet",
    amount=Decimal("15.0"),
    quantity=Decimal("2.0"),
    fees=Decimal("1.0"),
    tr_id="ORDER2",
)

ORDER3 = Disposal(
    datetime(2025, 1, 2),
    isin=ISIN("AAPL-ISIN"),
    ticker=Ticker("AAPL"),
    name="Apple",
    amount=Decimal("1.0"),
    quantity=Decimal("1.0"),
    tr_id="ORDER3",
)

ORDER4 = Disposal(
    datetime(2025, 1, 3),
    isin=ISIN("AAPL-ISIN"),
    ticker=Ticker("AAPL"),
    name="Apple",
    amount=Decimal("1.0"),
    quantity=Decimal("1.0"),
    tr_id="ORDER4",
)

DIVIDEND1 = Dividend(
    datetime(2023, 2, 5, 14, 7, 20),
    isin=ISIN("AMZN-ISIN"),
    ticker=Ticker("AMZN"),
    name="Amazon",
    amount=Decimal("5.0"),
    withheld=Decimal("2.0"),
)

DIVIDEND2 = Dividend(
    datetime(2024, 2, 5, 14, 7, 20),
    isin=ISIN("GOOG-ISIN"),
    ticker=Ticker("GOOG"),
    name="Alphabet",
    amount=Decimal("5.0"),
    withheld=Decimal("2.0"),
)

TRANSFER1 = Transfer(datetime(2023, 2, 5, 14, 7, 20), Decimal("3000.0"))

TRANSFER2 = Transfer(datetime(2024, 2, 5, 14, 7, 20), Decimal("-1000.0"))

INTEREST1 = Interest(datetime(2023, 2, 5, 14, 7, 20), Decimal("1000.0"))

INTEREST2 = Interest(datetime(2024, 2, 5, 14, 7, 20), Decimal("500.0"))


def test_trhistory_duplicates_on_different_files_are_removed():
    # Create an order almost identical to ORDER1 other than the
    # `number` field which is automatically populated and it will be
    # different. For comparison purposes, the orders should be
    # equivalent.
    order1b = replace(ORDER1)

    tr_hist = TrHistory(
        orders=[ORDER1, order1b],
        dividends=[DIVIDEND1, DIVIDEND1],
        transfers=[TRANSFER1, TRANSFER1],
        interest=[INTEREST1, INTEREST1],
    )

    assert len(tr_hist.orders) == 1
    assert len(tr_hist.dividends) == 1
    assert len(tr_hist.transfers) == 1
    assert len(tr_hist.interest) == 1


def test_trhistory_transactions_are_sorted_by_timestamp():
    tr_hist = TrHistory(orders=[ORDER2, ORDER1])

    orders = tr_hist.orders
    assert len(orders) == 2
    assert orders[0].isin == ORDER1.isin
    assert orders[1].isin == ORDER2.isin


def test_trhistory_dividends_are_sorted_by_timestamp():
    tr_hist = TrHistory(dividends=[DIVIDEND2, DIVIDEND1])

    dividends = tr_hist.dividends
    assert len(dividends) == 2
    assert dividends[0].isin == DIVIDEND1.isin
    assert dividends[1].isin == DIVIDEND2.isin


def test_trhistory_transfers_are_sorted_by_timestamp():
    tr_hist = TrHistory(transfers=[TRANSFER2, TRANSFER1])

    transfers = tr_hist.transfers
    assert len(transfers) == 2
    assert transfers[0].amount == Decimal("3000")
    assert transfers[1].amount == Decimal("-1000")


def test_trhistory_interest_is_sorted_by_timestamp():
    tr_hist = TrHistory(interest=[INTEREST2, INTEREST1])

    interest = tr_hist.interest
    assert len(interest) == 2
    assert interest[0].amount == INTEREST1.amount
    assert interest[1].amount == INTEREST2.amount


def test_trhistory_securities():
    tr_hist = TrHistory(orders=[ORDER1, ORDER2, ORDER3, ORDER4])
    assert tuple(tr_hist.securities) == (
        ("GOOG-ISIN", "Alphabet"),
        ("AMZN-ISIN", "Amazon"),
        ("AAPL-ISIN", "Apple"),
    )


def test_get_security_name():
    tr_hist = TrHistory(orders=[ORDER1, ORDER2, ORDER3, ORDER4])
    assert tr_hist.get_security_name(ISIN("AMZN-ISIN")) == "Amazon"
    assert tr_hist.get_security_name(ISIN("GOOG-ISIN")) == "Alphabet"
    assert tr_hist.get_security_name(ISIN("AAPL-ISIN")) == "Apple"
    assert tr_hist.get_security_name(ISIN("NOTF")) is None


def test_get_ticker_isin():
    tr_hist = TrHistory(orders=[ORDER1, ORDER2, ORDER3, ORDER4])
    assert tr_hist.get_ticker_isin(Ticker("AMZN")) == ISIN("AMZN-ISIN")
    assert tr_hist.get_ticker_isin(Ticker("GOOG")) == ISIN("GOOG-ISIN")
    assert tr_hist.get_ticker_isin(Ticker("AAPL")) == ISIN("AAPL-ISIN")
    assert tr_hist.get_ticker_isin(Ticker("NOTF")) is None


def test_get_ticker_isin_when_ticker_ambigous():
    order1 = Acquisition(
        datetime(2023, 1, 1),
        isin=ISIN("NL0010273215"),
        ticker=Ticker("ASML"),
        amount=Decimal("10.0"),
        quantity=Decimal("1.0"),
    )

    order2 = Acquisition(
        datetime(2023, 1, 2),
        isin=ISIN("USN070592100"),
        ticker=Ticker("ASML"),
        amount=Decimal("10.0"),
        quantity=Decimal("1.0"),
    )

    tr_hist = TrHistory(orders=[order1, order2])
    with pytest.raises(AmbiguousTickerError):
        tr_hist.get_ticker_isin(Ticker("ASML"))


def test_trhistory_show_orders(capsys):
    tr_hist = TrHistory(orders=[ORDER1, ORDER2])
    tr_hist.show_orders()
    captured = capsys.readouterr()
    assert ORDER1.name in captured.out
    assert ORDER2.name in captured.out


def test_trhistory_show_dividends(capsys):
    tr_hist = TrHistory(dividends=[DIVIDEND1, DIVIDEND2])
    tr_hist.show_dividends()
    captured = capsys.readouterr()
    assert DIVIDEND1.name in captured.out
    assert DIVIDEND2.name in captured.out


def test_trhistory_show_transfers(capsys):
    tr_hist = TrHistory(transfers=[TRANSFER1, TRANSFER2])
    tr_hist.show_transfers()
    captured = capsys.readouterr()
    assert str(TRANSFER1.amount) in captured.out
    assert str(abs(TRANSFER2.amount)) in captured.out


def test_trhistory_show_interest(capsys):
    tr_hist = TrHistory(interest=[INTEREST1, INTEREST2])
    tr_hist.show_interest()
    captured = capsys.readouterr()
    assert str(INTEREST1.amount) in captured.out
    assert str(INTEREST2.amount) in captured.out
