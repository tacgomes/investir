from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from investir.fees import Fees
from investir.findata import Split
from investir.transaction import Acquisition, Disposal, Order
from investir.typing import ISIN, Ticker
from investir.utils import sterling


def test_acquisition_order():
    count = Order.order_count

    order = Acquisition(
        datetime(2022, 4, 6, 18, 4, 50),
        isin=ISIN("AMZN-ISIN"),
        ticker=Ticker("AMZN"),
        name="Amazon",
        quantity=Decimal("20.0"),
        total=sterling("101.4"),
        fees=Fees(stamp_duty=sterling("1.4")),
        tr_id="ORDER",
    )

    assert order.date == date(2022, 4, 6)
    assert order.tax_year() == 2023
    assert order.number == count + 1
    assert order.price == order.cost_before_fees / order.quantity
    assert order.cost_before_fees == order.total - order.fees.total


def test_disposal_order():
    count = Order.order_count

    order = Disposal(
        datetime(2023, 4, 6, 18, 4, 50),
        isin=ISIN("AMZN-ISIN"),
        ticker=Ticker("AMZN"),
        name="Amazon",
        quantity=Decimal("10.0"),
        total=sterling("48.3"),
        fees=Fees(stamp_duty=sterling("1.7")),
        tr_id="ORDER",
    )

    assert order.date == date(2023, 4, 6)
    assert order.tax_year() == 2024
    assert order.number == count + 1
    assert order.price == order.gross_proceeds / order.quantity
    assert order.gross_proceeds == order.total + order.fees.total


def test_order_merge():
    order1 = Acquisition(
        datetime(2022, 4, 6, 18, 4, 50),
        isin=ISIN("AMZN-ISIN"),
        ticker=Ticker("AMZN"),
        name="Amazon",
        total=sterling("101.4"),
        quantity=Decimal("20.0"),
        fees=Fees(stamp_duty=sterling("1.4")),
    )

    order2 = Acquisition(
        datetime(2022, 4, 6, 18, 4, 50),
        isin=ISIN("AMZN-ISIN"),
        ticker=Ticker("AMZN"),
        name="Amazon",
        total=sterling("51.5"),
        quantity=Decimal("5.0"),
        fees=Fees(stamp_duty=sterling("1.5")),
    )

    order3 = Acquisition(
        datetime(2022, 4, 6, 18, 4, 50),
        isin=ISIN("AMZN-ISIN"),
        ticker=Ticker("AMZN"),
        name="Amazon",
        total=sterling("10.1"),
        quantity=Decimal("4.0"),
        fees=Fees(stamp_duty=sterling("0.1")),
    )

    merged_order = Order.merge(order1, order2, order3)
    assert merged_order.timestamp == datetime(2022, 4, 6, 0, 0)
    assert merged_order.isin == ISIN("AMZN-ISIN")
    assert merged_order.ticker == Ticker("AMZN")
    assert merged_order.name == "Amazon"
    assert merged_order.total == sterling("163.0")
    assert merged_order.quantity == Decimal("29.0")
    assert merged_order.fees.total == sterling("3.0")


def test_order_split():
    date_time = datetime(2022, 4, 6, 18, 4, 50)

    order = Acquisition(
        date_time,
        isin=ISIN("AMZN-ISIN"),
        ticker=Ticker("AMZN"),
        name="Amazon",
        total=sterling("126.0"),
        quantity=Decimal("12.0"),
        fees=Fees(stamp_duty=sterling("6.0")),
    )

    matched, remainder = order.split(Decimal("8.0"))

    assert isinstance(matched, Acquisition)
    assert matched.timestamp == date_time
    assert matched.isin == ISIN("AMZN-ISIN")
    assert matched.ticker == Ticker("AMZN")
    assert matched.name == "Amazon"
    assert matched.total == sterling("84.0")
    assert matched.quantity == Decimal("8.0")
    assert matched.fees.total == sterling("4.0")

    assert isinstance(remainder, Acquisition)
    assert remainder.timestamp == date_time
    assert remainder.isin == ISIN("AMZN-ISIN")
    assert remainder.ticker == Ticker("AMZN")
    assert remainder.name == "Amazon"
    assert remainder.total == sterling("42.0")
    assert remainder.quantity == Decimal("4.0")
    assert remainder.fees.total == sterling("2.0")

    with pytest.raises(AssertionError):
        order.split(Decimal("12.1"))


def test_order_adjust_quantity():
    order1 = Acquisition(
        datetime(2018, 1, 1, tzinfo=timezone.utc),
        isin=ISIN("AMZN-ISIN"),
        name="Amazon",
        total=sterling("10.0"),
        quantity=Decimal("1.0"),
    )

    order2 = Acquisition(
        datetime(2020, 1, 1, tzinfo=timezone.utc),
        isin=ISIN("AMZN-ISIN"),
        name="Amazon",
        total=sterling("10.0"),
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
    assert order2_adjusted.total == order2.total
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
    assert order1_adjusted.total == order1.total
    assert order1_adjusted.fees == order1.fees
    assert order1_adjusted.quantity == order1.quantity * ratio
    assert order1_adjusted.original_quantity == order1.quantity
    assert order1_adjusted.tr_id == order1.tr_id
    assert "Adjusted from order" in order1_adjusted.notes
