from dataclasses import replace
from datetime import datetime
from decimal import Decimal

import pytest

from investir.exceptions import AmbiguousTickerError
from investir.fees import Fees
from investir.transaction import (
    Acquisition,
    Disposal,
    Dividend,
    Interest,
    Transfer,
)
from investir.trhistory import TransactionHistory
from investir.typing import ISIN, Ticker
from investir.utils import sterling

ORDER1 = Acquisition(
    datetime(2023, 4, 6, 18, 4, 50),
    isin=ISIN("AMZN-ISIN"),
    ticker=Ticker("AMZN"),
    name="Amazon",
    total=sterling("10.0"),
    quantity=Decimal("1.0"),
    fees=Fees(stamp_duty=sterling("0.5")),
    tr_id="ORDER1",
)

ORDER2 = Disposal(
    datetime(2024, 2, 5, 14, 7, 20),
    isin=ISIN("GOOG-ISIN"),
    ticker=Ticker("GOOG"),
    name="Alphabet",
    total=sterling("15.0"),
    quantity=Decimal("2.0"),
    fees=Fees(stamp_duty=sterling("1.0")),
    tr_id="ORDER2",
)

ORDER3 = Disposal(
    datetime(2025, 1, 2),
    isin=ISIN("AAPL-ISIN"),
    ticker=Ticker("AAPL"),
    name="Apple",
    total=sterling("1.0"),
    quantity=Decimal("1.0"),
    tr_id="ORDER3",
)

ORDER4 = Disposal(
    datetime(2025, 1, 3),
    isin=ISIN("AAPL-ISIN"),
    ticker=Ticker("AAPL"),
    name="Apple",
    total=sterling("1.0"),
    quantity=Decimal("1.0"),
    tr_id="ORDER4",
)

DIVIDEND1 = Dividend(
    datetime(2023, 2, 5, 14, 7, 20),
    isin=ISIN("AMZN-ISIN"),
    ticker=Ticker("AMZN"),
    name="Amazon",
    total=sterling("5.0"),
    withheld=sterling("2.0"),
)

DIVIDEND2 = Dividend(
    datetime(2024, 2, 5, 14, 7, 20),
    isin=ISIN("GOOG-ISIN"),
    ticker=Ticker("GOOG"),
    name="Alphabet",
    total=sterling("5.0"),
    withheld=sterling("2.0"),
)

TRANSFER1 = Transfer(datetime(2023, 2, 5, 14, 7, 20), sterling("3000.0"))

TRANSFER2 = Transfer(datetime(2024, 2, 5, 14, 7, 20), sterling("-1000.0"))

INTEREST1 = Interest(datetime(2023, 2, 5, 14, 7, 20), sterling("1000.0"))

INTEREST2 = Interest(datetime(2024, 2, 5, 14, 7, 20), sterling("500.0"))


def test_trhistory_duplicates_on_different_files_are_removed():
    # Create an order almost identical to ORDER1 other than the
    # `number` field which is automatically populated and it will be
    # different. For comparison purposes, the orders should be
    # equivalent.
    order1b = replace(ORDER1)

    trhistory = TransactionHistory(
        orders=[ORDER1, order1b],
        dividends=[DIVIDEND1, DIVIDEND1],
        transfers=[TRANSFER1, TRANSFER1],
        interest=[INTEREST1, INTEREST1],
    )

    assert len(trhistory.orders) == 1
    assert len(trhistory.dividends) == 1
    assert len(trhistory.transfers) == 1
    assert len(trhistory.interest) == 1


def test_trhistory_transactions_are_sorted_by_timestamp():
    trhistory = TransactionHistory(orders=[ORDER2, ORDER1])

    orders = trhistory.orders
    assert len(orders) == 2
    assert orders[0].isin == ORDER1.isin
    assert orders[1].isin == ORDER2.isin


def test_trhistory_dividends_are_sorted_by_timestamp():
    trhistory = TransactionHistory(dividends=[DIVIDEND2, DIVIDEND1])

    dividends = trhistory.dividends
    assert len(dividends) == 2
    assert dividends[0].isin == DIVIDEND1.isin
    assert dividends[1].isin == DIVIDEND2.isin


def test_trhistory_transfers_are_sorted_by_timestamp():
    trhistory = TransactionHistory(transfers=[TRANSFER2, TRANSFER1])

    transfers = trhistory.transfers
    assert len(transfers) == 2
    assert transfers[0].total == sterling("3000")
    assert transfers[1].total == sterling("-1000")


def test_trhistory_interest_is_sorted_by_timestamp():
    trhistory = TransactionHistory(interest=[INTEREST2, INTEREST1])

    interest = trhistory.interest
    assert len(interest) == 2
    assert interest[0].total == INTEREST1.total
    assert interest[1].total == INTEREST2.total


def test_trhistory_securities():
    trhistory = TransactionHistory(orders=[ORDER1, ORDER2, ORDER3, ORDER4])
    assert tuple(trhistory.securities) == (
        ("GOOG-ISIN", "Alphabet"),
        ("AMZN-ISIN", "Amazon"),
        ("AAPL-ISIN", "Apple"),
    )


def test_get_security_name():
    trhistory = TransactionHistory(orders=[ORDER1, ORDER2, ORDER3, ORDER4])
    assert trhistory.get_security_name(ISIN("AMZN-ISIN")) == "Amazon"
    assert trhistory.get_security_name(ISIN("GOOG-ISIN")) == "Alphabet"
    assert trhistory.get_security_name(ISIN("AAPL-ISIN")) == "Apple"
    assert trhistory.get_security_name(ISIN("NOTF")) is None


def test_get_ticker_isin():
    trhistory = TransactionHistory(orders=[ORDER1, ORDER2, ORDER3, ORDER4])
    assert trhistory.get_ticker_isin(Ticker("AMZN")) == ISIN("AMZN-ISIN")
    assert trhistory.get_ticker_isin(Ticker("GOOG")) == ISIN("GOOG-ISIN")
    assert trhistory.get_ticker_isin(Ticker("AAPL")) == ISIN("AAPL-ISIN")
    assert trhistory.get_ticker_isin(Ticker("NOTF")) is None


def test_get_ticker_isin_when_ticker_ambigous():
    order1 = Acquisition(
        datetime(2023, 1, 1),
        isin=ISIN("NL0010273215"),
        ticker=Ticker("ASML"),
        total=sterling("10.0"),
        quantity=Decimal("1.0"),
    )

    order2 = Acquisition(
        datetime(2023, 1, 2),
        isin=ISIN("USN070592100"),
        ticker=Ticker("ASML"),
        total=sterling("10.0"),
        quantity=Decimal("1.0"),
    )

    trhistory = TransactionHistory(orders=[order1, order2])
    with pytest.raises(AmbiguousTickerError):
        trhistory.get_ticker_isin(Ticker("ASML"))
