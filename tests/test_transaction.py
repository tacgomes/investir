from datetime import datetime
from decimal import Decimal

from investir.transaction import Order, Acquisition, Disposal


def test_acquisition_order():
    count = Order.order_count

    order = Acquisition(
        datetime(2022, 4, 6, 18, 4, 50),
        amount=Decimal('100.0'),
        ticker='AMZN',
        quantity=Decimal('20.0'),
        fees=Decimal('1.4'),
        order_id='ORDER')

    assert order.tax_year() == 2022
    assert order.id == count + 1
    assert order.price == order.amount / order.quantity
    assert order.total_cost == order.amount + order.fees


def test_disposal_order():
    count = Order.order_count

    order = Disposal(
        datetime(2023, 4, 6, 18, 4, 50),
        amount=Decimal('50.0'),
        ticker='AMZN',
        quantity=Decimal('10.0'),
        fees=Decimal('1.7'),
        order_id='ORDER')

    assert order.tax_year() == 2023
    assert order.id == count + 1
    assert order.price == order.amount / order.quantity
    assert order.net_proceeds == order.amount - order.fees
