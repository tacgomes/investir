from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from investir.findata import Split
from investir.transaction import Acquisition, Disposal, Order
from investir.typing import ISIN, Ticker


def test_acquisition_order():
    count = Order.order_count

    order = Acquisition(
        datetime(2022, 4, 6, 18, 4, 50),
        isin=ISIN("AMZN-ISIN"),
        ticker=Ticker("AMZN"),
        name="Amazon",
        amount=Decimal("100.0"),
        quantity=Decimal("20.0"),
        fees=Decimal("1.4"),
        tr_id="ORDER",
    )

    assert order.date == date(2022, 4, 6)
    assert order.tax_year() == 2022
    assert order.number == count + 1
    assert order.price == order.amount / order.quantity
    assert order.total_cost == order.amount + order.fees


def test_disposal_order():
    count = Order.order_count

    order = Disposal(
        datetime(2023, 4, 6, 18, 4, 50),
        isin=ISIN("AMZN-ISIN"),
        ticker=Ticker("AMZN"),
        name="Amazon",
        amount=Decimal("50.0"),
        quantity=Decimal("10.0"),
        fees=Decimal("1.7"),
        tr_id="ORDER",
    )

    assert order.date == date(2023, 4, 6)
    assert order.tax_year() == 2023
    assert order.number == count + 1
    assert order.price == order.amount / order.quantity
    assert order.net_proceeds == order.amount - order.fees


def test_order_merge():
    order1 = Acquisition(
        datetime(2022, 4, 6, 18, 4, 50),
        isin=ISIN("AMZN-ISIN"),
        ticker=Ticker("AMZN"),
        name="Amazon",
        amount=Decimal("100.0"),
        quantity=Decimal("20.0"),
        fees=Decimal("1.4"),
    )

    order2 = Acquisition(
        datetime(2022, 4, 6, 18, 4, 50),
        isin=ISIN("AMZN-ISIN"),
        ticker=Ticker("AMZN"),
        name="Amazon",
        amount=Decimal("50.0"),
        quantity=Decimal("5.0"),
        fees=Decimal("1.5"),
    )

    order3 = Acquisition(
        datetime(2022, 4, 6, 18, 4, 50),
        isin=ISIN("AMZN-ISIN"),
        ticker=Ticker("AMZN"),
        name="Amazon",
        amount=Decimal("10.0"),
        quantity=Decimal("4.0"),
        fees=Decimal("0.1"),
    )

    merged_order = Order.merge(order1, order2, order3)
    assert merged_order.timestamp == datetime(2022, 4, 6, 0, 0)
    assert merged_order.isin == ISIN("AMZN-ISIN")
    assert merged_order.ticker == Ticker("AMZN")
    assert merged_order.name == "Amazon"
    assert merged_order.amount == Decimal("160")
    assert merged_order.quantity == Decimal("29")
    assert merged_order.fees == Decimal("3.0")


def test_order_split():
    date_time = datetime(2022, 4, 6, 18, 4, 50)

    order = Acquisition(
        date_time,
        isin=ISIN("AMZN-ISIN"),
        ticker=Ticker("AMZN"),
        name="Amazon",
        amount=Decimal("120.0"),
        quantity=Decimal("12.0"),
        fees=Decimal("6.0"),
    )

    matched, remainder = order.split(Decimal("8.0"))

    assert isinstance(matched, Acquisition)
    assert matched.timestamp == date_time
    assert matched.isin == ISIN("AMZN-ISIN")
    assert matched.ticker == Ticker("AMZN")
    assert matched.name == "Amazon"
    assert matched.amount == Decimal("80.0")
    assert matched.quantity == Decimal("8.0")
    assert matched.fees == Decimal("4.0")

    assert isinstance(remainder, Acquisition)
    assert remainder.timestamp == date_time
    assert remainder.isin == ISIN("AMZN-ISIN")
    assert remainder.ticker == Ticker("AMZN")
    assert remainder.name == "Amazon"
    assert remainder.amount == Decimal("40.0")
    assert remainder.quantity == Decimal("4.0")
    assert remainder.fees == Decimal("2.0")

    with pytest.raises(AssertionError):
        order.split(Decimal("12.1"))


def test_order_adjust_quantity():
    order1 = Acquisition(
        datetime(2018, 1, 1, tzinfo=timezone.utc),
        isin=ISIN("AMZN-ISIN"),
        name="Amazon",
        amount=Decimal("10.0"),
        quantity=Decimal("1.0"),
    )

    order2 = Acquisition(
        datetime(2020, 1, 1, tzinfo=timezone.utc),
        isin=ISIN("AMZN-ISIN"),
        name="Amazon",
        amount=Decimal("10.0"),
        quantity=Decimal("1.0"),
    )

    splits = [
        Split(datetime(2019, 1, 1, tzinfo=timezone.utc), Decimal("10.0")),
        Split(datetime(2021, 1, 1, tzinfo=timezone.utc), Decimal("3.0")),
    ]

    order2_adjusted = order2.adjust_quantity(splits)
    ratio = Decimal("3.0")
    assert type(order2_adjusted) is type(order2)
    assert order2_adjusted.timestamp == order2.timestamp
    assert order2_adjusted.isin == order2.isin
    assert order2_adjusted.ticker == order2.ticker
    assert order2_adjusted.name == order2.name
    assert order2_adjusted.amount == order2.amount
    assert order2_adjusted.fees == order2.fees
    assert order2_adjusted.quantity == order2.quantity * ratio
    assert order2_adjusted.original_quantity == order2.quantity
    assert order2_adjusted.tr_id == order2.tr_id
    assert "Adjusted from order" in order2_adjusted.notes

    order1_adjusted = order1.adjust_quantity(splits)
    ratio = Decimal("10.0") * Decimal("3.0")
    assert type(order1_adjusted) is type(order1)
    assert order1_adjusted.timestamp == order1.timestamp
    assert order1_adjusted.isin == order1.isin
    assert order1_adjusted.ticker == order1.ticker
    assert order1_adjusted.name == order1.name
    assert order1_adjusted.amount == order1.amount
    assert order1_adjusted.fees == order1.fees
    assert order1_adjusted.quantity == order1.quantity * ratio
    assert order1_adjusted.original_quantity == order1.quantity
    assert order1_adjusted.tr_id == order1.tr_id
    assert "Adjusted from order" in order1_adjusted.notes
