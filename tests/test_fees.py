from decimal import Decimal

from moneyed import USD

from investir.const import BASE_CURRENCY
from investir.fees import Fees
from investir.utils import sterling

FEES = Fees(
    stamp_duty=sterling("4.0"),
    forex=sterling("3.0"),
    finra=sterling("0.4"),
    sec=sterling("0.1"),
)


def test_fees_none_set():
    assert Fees().total == BASE_CURRENCY.zero
    assert Fees(default_currency=USD).total == USD.zero


def test_fees_all_set():
    assert FEES.total == sterling("7.5")


def test_fees_all_set_add_sub():
    other_fees = Fees(
        stamp_duty=sterling("0.01"),
        forex=sterling("0.02"),
        finra=sterling("0.03"),
        sec=sterling("0.04"),
    )

    fees = FEES + other_fees
    assert fees.stamp_duty == sterling("4.01")
    assert fees.forex == sterling("3.02")
    assert fees.finra == sterling("0.43")
    assert fees.sec == sterling("0.14")

    assert fees - other_fees == FEES


def test_fees_none_set_add_sub():
    fees = Fees() - Fees()
    assert fees.stamp_duty is None
    assert fees.forex is None
    assert fees.finra is None
    assert fees.sec is None

    fees = Fees() + Fees()
    assert fees.stamp_duty is None
    assert fees.forex is None
    assert fees.finra is None
    assert fees.sec is None


def test_fees_some_set_add_sub():
    fees = FEES + Fees()
    assert fees.stamp_duty == sterling("4.0")
    assert fees.forex == sterling("3.0")
    assert fees.finra == sterling("0.4")
    assert fees.sec == sterling("0.1")

    fees = Fees() + FEES
    assert fees.stamp_duty == sterling("4.0")
    assert fees.forex == sterling("3.0")
    assert fees.finra == sterling("0.4")
    assert fees.sec == sterling("0.1")

    fees = FEES - Fees()
    assert fees.stamp_duty == sterling("4.0")
    assert fees.forex == sterling("3.0")
    assert fees.finra == sterling("0.4")
    assert fees.sec == sterling("0.1")

    fees = Fees() - FEES
    assert fees.stamp_duty == sterling("-4.0")
    assert fees.forex == sterling("-3.0")
    assert fees.finra == sterling("-0.4")
    assert fees.sec == sterling("-0.1")


def test_fees_all_set_mul_div():
    fees = FEES / Decimal("2.0")
    assert fees.stamp_duty == sterling("2.0")
    assert fees.forex == sterling("1.5")
    assert fees.finra == sterling("0.2")
    assert fees.sec == sterling("0.05")

    assert fees * Decimal("2.0") == FEES


def test_fees_none_set_mul_div():
    fees = Fees() / Decimal("2.0")
    assert fees.stamp_duty is None
    assert fees.forex is None
    assert fees.finra is None
    assert fees.sec is None

    fees = Fees() * Decimal("2.0")
    assert fees.stamp_duty is None
    assert fees.forex is None
    assert fees.finra is None
    assert fees.sec is None
