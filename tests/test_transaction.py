from datetime import datetime, date
from decimal import Decimal

import pytest

from investir.typing import Ticker
from investir.transaction import Order, Acquisition, Disposal


def test_acquisition_order():
    count = Order.order_count

    order = Acquisition(
        datetime(2022, 4, 6, 18, 4, 50),
        transaction_id="ORDER",
        amount=Decimal("100.0"),
        ticker=Ticker("AMZN"),
        quantity=Decimal("20.0"),
        fees=Decimal("1.4"),
    )

    assert order.date == date(2022, 4, 6)
    assert order.tax_year() == 2022
    assert order.id == count + 1
    assert order.price == order.amount / order.quantity
    assert order.total_cost == order.amount + order.fees


def test_disposal_order():
    count = Order.order_count

    order = Disposal(
        datetime(2023, 4, 6, 18, 4, 50),
        transaction_id="ORDER",
        amount=Decimal("50.0"),
        ticker=Ticker("AMZN"),
        quantity=Decimal("10.0"),
        fees=Decimal("1.7"),
    )

    assert order.date == date(2023, 4, 6)
    assert order.tax_year() == 2023
    assert order.id == count + 1
    assert order.price == order.amount / order.quantity
    assert order.net_proceeds == order.amount - order.fees


def test_order_merge():
    order1 = Acquisition(
        datetime(2022, 4, 6, 18, 4, 50),
        amount=Decimal("100.0"),
        ticker=Ticker("AMZN"),
        quantity=Decimal("20.0"),
        fees=Decimal("1.4"),
    )

    order2 = Acquisition(
        datetime(2022, 4, 6, 18, 4, 50),
        amount=Decimal("50.0"),
        ticker=Ticker("AMZN"),
        quantity=Decimal("5.0"),
        fees=Decimal("1.5"),
    )

    order3 = Acquisition(
        datetime(2022, 4, 6, 18, 4, 50),
        amount=Decimal("10.0"),
        ticker=Ticker("AMZN"),
        quantity=Decimal("4.0"),
        fees=Decimal("0.1"),
    )

    merged_order = Order.merge(order1, order2, order3)
    assert merged_order.timestamp == datetime(2022, 4, 6, 0, 0)
    assert merged_order.ticker == Ticker("AMZN")
    assert merged_order.amount == Decimal("160")
    assert merged_order.quantity == Decimal("29")
    assert merged_order.fees == Decimal("3.0")


def test_order_split():
    date_time = datetime(2022, 4, 6, 18, 4, 50)

    order = Acquisition(
        date_time,
        amount=Decimal("120.0"),
        ticker=Ticker("AMZN"),
        quantity=Decimal("12.0"),
        fees=Decimal("6.0"),
    )

    matched, remainder = order.split(Decimal("8.0"))

    assert isinstance(matched, Acquisition)
    assert matched.timestamp == date_time
    assert matched.ticker == Ticker("AMZN")
    assert matched.amount == Decimal("80.0")
    assert matched.quantity == Decimal("8.0")
    assert matched.fees == Decimal("4.0")

    assert isinstance(remainder, Acquisition)
    assert remainder.timestamp == date_time
    assert remainder.ticker == Ticker("AMZN")
    assert remainder.amount == Decimal("40.0")
    assert remainder.quantity == Decimal("4.0")
    assert remainder.fees == Decimal("2.0")

    with pytest.raises(AssertionError):
        order.split(Decimal("12.1"))
