from collections.abc import Callable, Sequence
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from iso4217 import Currency

from investir.config import config
from investir.exceptions import IncompleteRecordsError
from investir.findata import (
    DataProviderError,
    FinancialData,
    Price,
    SecurityInfo,
    Split,
    YahooFinanceExchangeRateProvider,
    YahooFinanceSecurityInfoProvider,
)
from investir.taxcalculator import TaxCalculator
from investir.transaction import Acquisition, Disposal, Order
from investir.trhistory import TrHistory
from investir.typing import ISIN, Ticker


@pytest.fixture(name="make_tax_calculator")
def _make_tax_calculator(mocker, tmp_path) -> Callable:
    def _method(
        orders: Sequence[Order],
        splits: Sequence[Split] | None = None,
        price: Price | Exception | None = None,
        fx_rate: Decimal | Exception | None = None,
    ) -> TaxCalculator:
        config.reset()

        if splits is None:
            splits = []
        else:
            assert all(orders[0].isin == o.isin for o in orders)

        security_info_provider = YahooFinanceSecurityInfoProvider()
        exchange_rate_provider = YahooFinanceExchangeRateProvider()
        mocker.patch.object(
            security_info_provider,
            "fech_info",
            return_value=SecurityInfo(splits=splits),
        )
        mocker.patch.object(
            security_info_provider,
            "fetch_price",
            side_effect=[price],
        )
        mocker.patch.object(
            exchange_rate_provider, "fetch_exchange_rate", side_effect=[fx_rate]
        )

        tr_hist = TrHistory(orders=orders)
        cache_file = tmp_path / "cache.yaml"

        financial_data = FinancialData(
            security_info_provider, exchange_rate_provider, tr_hist, cache_file
        )

        return TaxCalculator(tr_hist, financial_data)

    return _method


def test_section_104_disposal(make_tax_calculator):
    """
    Test Section 104 disposals using HMRC example:
      https://assets.publishing.service.gov.uk/media/65f993439316f5001164c2d7/HS284_Example_3_2024.pdf
    """
    order1 = Acquisition(
        datetime(2015, 4, 1, tzinfo=timezone.utc),
        isin=ISIN("LOBS"),
        quantity=Decimal("1000.0"),
        amount=Decimal("4000.0"),
        fees=Decimal("150.0"),
    )

    order2 = Acquisition(
        datetime(2018, 9, 1, tzinfo=timezone.utc),
        isin=ISIN("LOBS"),
        quantity=Decimal("500.0"),
        amount=Decimal("2050.0"),
        fees=Decimal("80.0"),
    )

    order3 = Disposal(
        datetime(2023, 5, 1, tzinfo=timezone.utc),
        isin=ISIN("LOBS"),
        quantity=Decimal("700.0"),
        amount=Decimal("3360.0"),
        fees=Decimal("100.0"),
    )

    order4 = Disposal(
        datetime(2024, 2, 1, tzinfo=timezone.utc),
        isin=ISIN("LOBS"),
        quantity=Decimal("400.0"),
        amount=Decimal("2080.0"),
        fees=Decimal("105.0"),
    )

    tax_calculator = make_tax_calculator([order1, order2, order3, order4])
    capital_gains = tax_calculator.capital_gains()
    assert len(capital_gains) == 2
    assert capital_gains == tax_calculator.capital_gains(2023)

    cg = capital_gains[0]
    assert cg.disposal.date == date(2023, 5, 1)
    assert cg.date_acquired is None
    assert cg.cost.quantize(Decimal("0.00")) == Decimal("3030.67")
    assert cg.gain_loss.quantize(Decimal("0.00")) == Decimal("329.33")
    assert str(cg) == (
        "2023-05-01 LOBS quantity: 700.0, cost: £3030.67"
        ", proceeds: £3360.0, gain: £329.33 (Section 104)"
    )

    cg = capital_gains[1]
    assert cg.disposal.date == date(2024, 2, 1)
    assert cg.date_acquired is None
    assert cg.cost.quantize(Decimal("0.00")) == Decimal("1779.67")
    assert cg.gain_loss.quantize(Decimal("0.00")) == Decimal("300.33")

    holding = tax_calculator.holding(Ticker("LOBS"))
    assert holding.quantity == Decimal("400.0")
    assert holding.cost.quantize(Decimal("0.00")) == Decimal("1674.67")


def test_section_104_with_no_disposal_made(make_tax_calculator):
    order1 = Acquisition(
        datetime(2015, 4, 1, tzinfo=timezone.utc),
        isin=ISIN("X"),
        quantity=Decimal("1000.0"),
        amount=Decimal("4000.0"),
        fees=Decimal("150.0"),
    )

    order2 = Acquisition(
        datetime(2018, 9, 1, tzinfo=timezone.utc),
        isin=ISIN("X"),
        quantity=Decimal("500.0"),
        amount=Decimal("2000.0"),
        fees=Decimal("50.0"),
    )

    tax_calculator = make_tax_calculator([order1, order2])
    holding = tax_calculator.holding(Ticker("X"))
    assert holding.quantity == Decimal("1500.0")
    assert holding.cost == Decimal("6200.0")


def test_same_day_rule(make_tax_calculator):
    order1 = Acquisition(
        datetime(2018, 1, 1, tzinfo=timezone.utc),
        isin=ISIN("X"),
        quantity=Decimal("10.0"),
        amount=Decimal("100.0"),
    )

    order2 = Disposal(
        datetime(2019, 1, 20, 14, 0, tzinfo=timezone.utc),
        isin=ISIN("X"),
        quantity=Decimal("1.0"),
        amount=Decimal("70.0"),
    )

    order3 = Acquisition(
        datetime(2019, 1, 20, 15, 0, tzinfo=timezone.utc),
        isin=ISIN("X"),
        quantity=Decimal("1.0"),
        amount=Decimal("60.0"),
    )

    order4 = Acquisition(
        datetime(2019, 1, 20, 16, 0, tzinfo=timezone.utc),
        isin=ISIN("X"),
        quantity=Decimal("2.0"),
        amount=Decimal("65.0"),
    )

    order5 = Disposal(
        datetime(2019, 1, 20, 17, 0, tzinfo=timezone.utc),
        isin=ISIN("X"),
        quantity=Decimal("4.0"),
        amount=Decimal("280.0"),
    )

    order6 = Acquisition(
        datetime(2019, 1, 20, 18, 0, tzinfo=timezone.utc),
        isin=ISIN("X"),
        quantity=Decimal("2.0"),
        amount=Decimal("55.0"),
    )

    tax_calculator = make_tax_calculator(
        [order1, order2, order3, order4, order5, order6]
    )
    capital_gains = tax_calculator.capital_gains()
    assert len(capital_gains) == 1

    cg = capital_gains[0]
    assert cg.date_acquired == date(2019, 1, 20)
    assert cg.disposal.amount == order2.amount + order5.amount
    assert cg.cost == order3.amount + order4.amount + order6.amount
    assert cg.gain_loss == Decimal("170.00")

    holding = tax_calculator.holding(Ticker("X"))
    assert holding.quantity == Decimal("10.0")
    assert holding.cost == Decimal("100.0")


@pytest.mark.parametrize("days_elapsed", range(1, 31))
def test_bed_and_breakfast_rule(days_elapsed, make_tax_calculator):
    order1 = Acquisition(
        datetime(2019, 1, 18, tzinfo=timezone.utc),
        isin=ISIN("X"),
        quantity=Decimal("10.0"),
        amount=Decimal("100.0"),
    )

    order2 = Disposal(
        datetime(2019, 1, 20, tzinfo=timezone.utc),
        isin=ISIN("X"),
        quantity=Decimal("5.0"),
        amount=Decimal("150.0"),
    )

    order3 = Acquisition(
        order2.timestamp + timedelta(days=days_elapsed),
        isin=ISIN("X"),
        quantity=Decimal("5.0"),
        amount=Decimal("120.0"),
    )

    tax_calculator = make_tax_calculator([order1, order2, order3])
    capital_gains = tax_calculator.capital_gains()
    assert len(capital_gains) == 1

    cg = capital_gains[0]
    assert cg.date_acquired == order2.date + timedelta(days=days_elapsed)
    assert cg.cost == Decimal("120.0")
    assert cg.gain_loss == Decimal("30.0")
    assert str(cg) == (
        f"2019-01-20 X    quantity: 5.0, cost: £120.00"
        f", proceeds: £150.0, gain: £30.00 ({cg.date_acquired})"
    )

    holding = tax_calculator.holding(Ticker("X"))
    assert holding.quantity == Decimal("10")
    assert holding.cost == Decimal("100.0")


def test_acquisitions_are_not_matched_after_thirty_days_of_disposal_date(
    make_tax_calculator,
):
    order1 = Acquisition(
        datetime(2018, 1, 1, tzinfo=timezone.utc),
        isin=ISIN("X"),
        quantity=Decimal("10.0"),
        amount=Decimal("100.0"),
    )

    order2 = Disposal(
        datetime(2019, 1, 19, tzinfo=timezone.utc),
        isin=ISIN("X"),
        quantity=Decimal("5.0"),
        amount=Decimal("150.0"),
    )

    order3 = Acquisition(
        datetime(2019, 2, 19, tzinfo=timezone.utc),
        isin=ISIN("X"),
        quantity=Decimal("5.0"),
        amount=Decimal("120.0"),
    )

    tax_calculator = make_tax_calculator([order1, order2, order3])
    capital_gains = tax_calculator.capital_gains()
    assert len(capital_gains) == 1

    cg = capital_gains[0]
    assert cg.date_acquired is None
    assert cg.cost == Decimal("50.0")
    assert cg.gain_loss == Decimal("100.0")

    holding = tax_calculator.holding(Ticker("X"))
    assert holding.quantity == Decimal("10")
    assert holding.cost == Decimal("170.0")


def test_acquisitions_are_not_matched_before_disposal_date(make_tax_calculator):
    order1 = Acquisition(
        datetime(2018, 1, 1, tzinfo=timezone.utc),
        isin=ISIN("X"),
        quantity=Decimal("10.0"),
        amount=Decimal("100.0"),
    )

    order2 = Acquisition(
        datetime(2019, 2, 18, tzinfo=timezone.utc),
        isin=ISIN("X"),
        quantity=Decimal("5.0"),
        amount=Decimal("200.0"),
    )

    order3 = Disposal(
        datetime(2019, 2, 19, tzinfo=timezone.utc),
        isin=ISIN("X"),
        quantity=Decimal("5.0"),
        amount=Decimal("150.0"),
    )

    tax_calculator = make_tax_calculator([order1, order2, order3])
    capital_gains = tax_calculator.capital_gains()
    assert len(capital_gains) == 1

    cg = capital_gains[0]
    assert cg.date_acquired is None
    assert cg.cost == Decimal("100.00")
    assert cg.gain_loss == Decimal("50.0")

    holding = tax_calculator.holding(Ticker("X"))
    assert holding.quantity == Decimal("10")
    assert holding.cost == Decimal("200.0")


def test_same_day_rule_has_priority_to_bed_and_breakfast_rule(make_tax_calculator):
    """
    Verify that the same day rule has priority over the
    bed and breakfast rule. Note that in the list of
    tax events the bed and breakfast disposal is shown
    first due the earlier disposal date.
    """
    order1 = Acquisition(
        datetime(2018, 1, 1, tzinfo=timezone.utc),
        isin=ISIN("X"),
        quantity=Decimal("10.0"),
        amount=Decimal("100.0"),
    )

    order2 = Disposal(
        datetime(2019, 1, 20, tzinfo=timezone.utc),
        isin=ISIN("X"),
        quantity=Decimal("5.0"),
        amount=Decimal("150.0"),
    )

    order3 = Acquisition(
        datetime(2019, 1, 25, tzinfo=timezone.utc),
        isin=ISIN("X"),
        quantity=Decimal("5.0"),
        amount=Decimal("150.0"),
    )

    order4 = Disposal(
        datetime(2019, 1, 25, tzinfo=timezone.utc),
        isin=ISIN("X"),
        quantity=Decimal("5.0"),
        amount=Decimal("170.0"),
    )

    order5 = Acquisition(
        datetime(2019, 1, 27, tzinfo=timezone.utc),
        isin=ISIN("X"),
        quantity=Decimal("5.0"),
        amount=Decimal("300.0"),
    )

    tax_calculator = make_tax_calculator([order1, order2, order3, order4, order5])
    capital_gains = tax_calculator.capital_gains()
    assert len(capital_gains) == 2

    cg = capital_gains[0]  # Bed and breakfast disposal event
    assert cg.date_acquired == date(2019, 1, 27)
    assert cg.cost == Decimal("300.0")
    assert cg.gain_loss == Decimal("-150.0")

    cg = capital_gains[1]  # Same day disposal event
    assert cg.date_acquired == date(2019, 1, 25)
    assert cg.cost == Decimal("150.0")
    assert cg.gain_loss == Decimal("20.0")

    holding = tax_calculator.holding(Ticker("X"))
    assert holding.quantity == Decimal("10.0")
    assert holding.cost == Decimal("100.0")


def test_matching_disposals_with_larger_acquisition(make_tax_calculator):
    """
    Test splitting an acquisition in two to match the first disposal,
    and then using the remaining part to match the second disposal.
    """
    order1 = Acquisition(
        datetime(2018, 1, 1, tzinfo=timezone.utc),
        isin=ISIN("X"),
        quantity=Decimal("10.0"),
        amount=Decimal("100.0"),
    )

    order2 = Disposal(
        datetime(2019, 1, 20, tzinfo=timezone.utc),
        isin=ISIN("X"),
        quantity=Decimal("5.0"),
        amount=Decimal("60.0"),
    )

    order3 = Disposal(
        datetime(2019, 1, 21, tzinfo=timezone.utc),
        isin=ISIN("X"),
        quantity=Decimal("1.0"),
        amount=Decimal("11.0"),
    )

    order4 = Acquisition(
        datetime(2019, 1, 22, tzinfo=timezone.utc),
        isin=ISIN("X"),
        quantity=Decimal("7.0"),
        amount=Decimal("70.0"),
    )

    tax_calculator = make_tax_calculator([order1, order2, order3, order4])
    capital_gains = tax_calculator.capital_gains()
    assert len(capital_gains) == 2

    cg = capital_gains[0]
    assert cg.date_acquired == date(2019, 1, 22)
    assert cg.cost == Decimal("50.0")
    assert cg.gain_loss == Decimal("10.0")

    cg = capital_gains[1]
    assert cg.date_acquired == date(2019, 1, 22)
    assert cg.cost == Decimal("10.0")
    assert cg.gain_loss == Decimal("1.0")

    holding = tax_calculator.holding(Ticker("X"))
    assert holding.quantity == Decimal("11.0")
    assert holding.cost == Decimal("110.0")


def test_matching_disposal_with_multiple_smaller_acquisitions(make_tax_calculator):
    """
    Test multiple tax events derived from a single disposal
       - 1 share matched due same day rule
       - 2 shares matched due bed and breakfast rule on 2019/1/25
       - 1 shares matched due bed and breakfast rule on 2019/1/27
       - 1 share from the Section 104 pool

    In addition, verify that the second disposal does not match
    against acquisitions that were already matched for the first
    disposal.
    """
    order1 = Acquisition(
        datetime(2018, 1, 1, tzinfo=timezone.utc),
        isin=ISIN("X"),
        quantity=Decimal("10.0"),
        amount=Decimal("30.0"),
    )

    order2 = Disposal(
        datetime(2019, 1, 20, tzinfo=timezone.utc),
        isin=ISIN("X"),
        quantity=Decimal("5.0"),
        amount=Decimal("50.0"),
    )

    order3 = Acquisition(
        datetime(2019, 1, 20, tzinfo=timezone.utc),
        isin=ISIN("X"),
        quantity=Decimal("1.0"),
        amount=Decimal("9.0"),
    )

    order4 = Acquisition(
        datetime(2019, 1, 25, tzinfo=timezone.utc),
        isin=ISIN("X"),
        quantity=Decimal("2.0"),
        amount=Decimal("16.0"),
    )

    order5 = Acquisition(
        datetime(2019, 1, 27, tzinfo=timezone.utc),
        isin=ISIN("X"),
        quantity=Decimal("1.0"),
        amount=Decimal("5.0"),
    )

    order6 = Disposal(
        datetime(2019, 3, 1, tzinfo=timezone.utc),
        isin=ISIN("X"),
        quantity=Decimal("1.0"),
        amount=Decimal("7.0"),
    )

    tax_calculator = make_tax_calculator(
        [order1, order2, order3, order4, order5, order6]
    )
    capital_gains = tax_calculator.capital_gains()
    assert len(capital_gains) == 5

    cg = capital_gains[0]  # Same day
    assert cg.date_acquired == date(2019, 1, 20)
    assert cg.cost == Decimal("9.0")
    assert cg.gain_loss == Decimal("1.0")

    cg = capital_gains[1]  # First bed and breakfast match
    assert cg.date_acquired == date(2019, 1, 25)
    assert cg.cost == Decimal("16.0")
    assert cg.gain_loss == Decimal("4.0")

    cg = capital_gains[2]  # Second bed and breakfast match
    assert cg.date_acquired == date(2019, 1, 27)
    assert cg.cost == Decimal("5.0")
    assert cg.gain_loss == Decimal("5.0")

    cg = capital_gains[3]  # Section 104 pool
    assert cg.date_acquired is None
    assert cg.cost == Decimal("3.0")
    assert cg.gain_loss == Decimal("7.0")

    cg = capital_gains[4]  # Section 104 pool
    assert cg.date_acquired is None
    assert cg.cost == Decimal("3.0")
    assert cg.gain_loss == Decimal("4.0")

    holding = tax_calculator.holding(Ticker("X"))
    assert holding.quantity == Decimal("8.0")
    assert holding.cost == Decimal("24.0")


def test_capital_gains_on_orders_with_fees_included(make_tax_calculator):
    order1 = Acquisition(
        datetime(2018, 1, 1, tzinfo=timezone.utc),
        isin=ISIN("X"),
        quantity=Decimal("10.0"),
        amount=Decimal("30.0"),
        fees=Decimal("1.5"),
    )

    order2 = Acquisition(
        datetime(2019, 1, 20, tzinfo=timezone.utc),
        isin=ISIN("X"),
        quantity=Decimal("5.0"),
        amount=Decimal("40.0"),
        fees=Decimal("0.5"),
    )

    order3 = Disposal(
        datetime(2019, 1, 20, tzinfo=timezone.utc),
        isin=ISIN("X"),
        quantity=Decimal("5.0"),
        amount=Decimal("50.0"),
        fees=Decimal("0.4"),
    )

    order4 = Disposal(
        datetime(2019, 3, 1, tzinfo=timezone.utc),
        isin=ISIN("X"),
        quantity=Decimal("5.0"),
        amount=Decimal("50.0"),
        fees=Decimal("0.8"),
    )

    tax_calculator = make_tax_calculator([order1, order2, order3, order4])
    capital_gains = tax_calculator.capital_gains()
    assert len(capital_gains) == 2

    # Acquisition cost = 40.0 + 0.4 + 0.5 = 40.9
    # Gain/Loss        = 50.0 - 40.9 = 33.45 = 9.1
    cg = capital_gains[1]
    cg = capital_gains[0]
    assert cg.date_acquired == date(2019, 1, 20)
    assert cg.cost == Decimal("40.9")
    assert cg.gain_loss == Decimal("9.1")

    # S104 pool cost   = 30.0 + 1.5 = 31.5
    # Acquisition cost = 31.5 * (5.0/10.0) + 0.8 = 16.55
    # Gain/Loss        = 50.0 - 16.55 = 33.45
    cg = capital_gains[1]
    assert cg.date_acquired is None
    assert cg.cost == Decimal("16.55")
    assert cg.gain_loss == Decimal("33.45")

    # New S104 pool cost = 31.5 - 31.5 * (5.0/10.0) = 15.75
    holding = tax_calculator.holding(Ticker("X"))
    assert holding.quantity == Decimal("5.0")
    assert holding.cost == Decimal("15.75")


def test_disposals_on_different_tickers(make_tax_calculator):
    order1 = Acquisition(
        datetime(2018, 1, 1, tzinfo=timezone.utc),
        isin=ISIN("X"),
        quantity=Decimal("10.0"),
        amount=Decimal("100.0"),
    )

    order2 = Acquisition(
        datetime(2018, 1, 1, tzinfo=timezone.utc),
        isin=ISIN("Y"),
        quantity=Decimal("20.0"),
        amount=Decimal("200.0"),
    )

    order3 = Disposal(
        datetime(2019, 1, 20, tzinfo=timezone.utc),
        isin=ISIN("X"),
        quantity=Decimal("1.0"),
        amount=Decimal("11.0"),
    )

    order4 = Disposal(
        datetime(2019, 1, 21, tzinfo=timezone.utc),
        isin=ISIN("Y"),
        quantity=Decimal("2.0"),
        amount=Decimal("22.0"),
    )

    order5 = Acquisition(
        datetime(2019, 1, 21, tzinfo=timezone.utc),
        isin=ISIN("X"),
        quantity=Decimal("2.0"),
        amount=Decimal("8.0"),
    )

    order6 = Acquisition(
        datetime(2019, 1, 22, tzinfo=timezone.utc),
        isin=ISIN("Y"),
        quantity=Decimal("2.0"),
        amount=Decimal("6.0"),
    )

    tax_calculator = make_tax_calculator(
        [order1, order2, order3, order4, order5, order6]
    )
    capital_gains = tax_calculator.capital_gains()
    assert len(capital_gains) == 2

    cg = capital_gains[0]
    assert cg.date_acquired == date(2019, 1, 21)
    assert cg.disposal.isin == ISIN("X")
    assert cg.cost == Decimal("4.0")
    assert cg.gain_loss == Decimal("7.0")

    cg = capital_gains[1]
    assert cg.date_acquired == date(2019, 1, 22)
    assert cg.disposal.isin == ISIN("Y")
    assert cg.cost == Decimal("6.0")
    assert cg.gain_loss == Decimal("16.0")

    holding = tax_calculator.holding(Ticker("X"))
    assert holding.quantity == Decimal("11.0")
    assert holding.cost == Decimal("104.0")

    holding = tax_calculator.holding(Ticker("Y"))
    assert holding.quantity == Decimal("20.0")
    assert holding.cost == Decimal("200.0")


def test_integrity_disposal_without_acquisition(make_tax_calculator):
    order = Disposal(
        datetime(2019, 1, 17, tzinfo=timezone.utc),
        isin=ISIN("X"),
        quantity=Decimal("5.0"),
        amount=Decimal("120.0"),
    )

    tax_calculator = make_tax_calculator([order])
    with pytest.raises(IncompleteRecordsError):
        tax_calculator.capital_gains()

    tax_calculator = make_tax_calculator([order])
    config.strict = False
    tax_calculator.capital_gains()


def test_integrity_disposing_more_than_quantity_acquired(make_tax_calculator):
    order1 = Acquisition(
        datetime(2019, 1, 18, tzinfo=timezone.utc),
        isin=ISIN("X"),
        quantity=Decimal("5.0"),
        amount=Decimal("100.0"),
    )

    order2 = Disposal(
        datetime(2019, 3, 17, tzinfo=timezone.utc),
        isin=ISIN("X"),
        quantity=Decimal("10.0"),
        amount=Decimal("120.0"),
    )

    tax_calculator = make_tax_calculator([order1, order2])
    with pytest.raises(IncompleteRecordsError):
        tax_calculator.capital_gains()

    tax_calculator = make_tax_calculator([order1, order2])
    config.strict = False
    tax_calculator.capital_gains()


def test_section_104_disposal_with_share_split(make_tax_calculator):
    order1 = Acquisition(
        datetime(2014, 5, 1, tzinfo=timezone.utc),
        isin=ISIN("X"),
        quantity=Decimal("11.0"),
        amount=Decimal("3300.0"),
    )

    order2 = Disposal(
        datetime(2014, 6, 1, tzinfo=timezone.utc),
        isin=ISIN("X"),
        quantity=Decimal("1.0"),
        amount=Decimal("500.0"),
    )

    order3 = Acquisition(
        datetime(2014, 8, 1, tzinfo=timezone.utc),
        isin=ISIN("X"),
        quantity=Decimal("10.0"),
        amount=Decimal("1000.0"),
    )

    order4 = Disposal(
        datetime(2014, 9, 1, tzinfo=timezone.utc),
        isin=ISIN("X"),
        quantity=Decimal("5.0"),
        amount=Decimal("1100.0"),
    )

    tax_calculator = make_tax_calculator(
        [order1, order2, order3, order4],
        [Split(datetime(2014, 7, 1, tzinfo=timezone.utc), Decimal("3.0"))],
    )
    capital_gains = tax_calculator.capital_gains()
    assert len(capital_gains) == 2

    cg = capital_gains[0]
    assert cg.disposal.date == date(2014, 6, 1)
    assert cg.date_acquired is None
    assert cg.cost == Decimal("300.0")
    assert cg.quantity == Decimal("1.0")
    assert cg.gain_loss == Decimal("200.0")

    cg = capital_gains[1]
    assert cg.disposal.date == date(2014, 9, 1)
    assert cg.date_acquired is None
    assert cg.cost == Decimal("500.0")
    assert cg.quantity == Decimal("5.0")
    assert cg.gain_loss == Decimal("600.0")

    holding = tax_calculator.holding(Ticker("X"))
    assert holding.quantity == Decimal("35.0")
    assert holding.cost == Decimal("3500.0")


def test_bed_and_breakfast_rule_with_share_split(make_tax_calculator):
    order1 = Acquisition(
        datetime(2019, 1, 18, tzinfo=timezone.utc),
        isin=ISIN("X"),
        quantity=Decimal("10.0"),
        amount=Decimal("100.0"),
    )

    order2 = Disposal(
        datetime(2019, 1, 20, tzinfo=timezone.utc),
        isin=ISIN("X"),
        quantity=Decimal("5.0"),
        amount=Decimal("150.0"),
    )

    order3 = Acquisition(
        datetime(2019, 1, 30, tzinfo=timezone.utc),
        isin=ISIN("X"),
        quantity=Decimal("20.0"),
        amount=Decimal("160.0"),
    )

    tax_calculator = make_tax_calculator(
        [order1, order2, order3],
        [Split(datetime(2019, 1, 25, tzinfo=timezone.utc), Decimal("3.0"))],
    )
    capital_gains = tax_calculator.capital_gains()
    assert len(capital_gains) == 1

    cg = capital_gains[0]
    assert cg.date_acquired == order3.date
    assert cg.cost == Decimal("120.0")
    assert cg.quantity == Decimal("5.0")
    assert cg.gain_loss == Decimal("30.0")

    holding = tax_calculator.holding(Ticker("X"))
    assert holding.quantity == Decimal("35.0")
    assert holding.cost == Decimal("140.0")


def test_rppaccounts_example(make_tax_calculator):
    """
    Rawlinson Pryde & Partners Accountants calculation example:
    https://rppaccounts.co.uk/taxation-of-shares/
    """
    order1 = Acquisition(
        datetime(2019, 1, 18, tzinfo=timezone.utc),
        isin=ISIN("X"),
        quantity=Decimal("4.0"),
        amount=Decimal("12025.0"),
    )

    order2 = Disposal(
        datetime(2019, 1, 18, tzinfo=timezone.utc),
        isin=ISIN("X"),
        quantity=Decimal("3.0"),
        amount=Decimal("9100.0"),
    )

    order3 = Disposal(
        datetime(2019, 1, 19, tzinfo=timezone.utc),
        isin=ISIN("X"),
        quantity=Decimal("1.0"),
        amount=Decimal("5000.0"),
    )

    order4 = Acquisition(
        datetime(2019, 1, 22, tzinfo=timezone.utc),
        isin=ISIN("X"),
        quantity=Decimal("1.0"),
        amount=Decimal("2000.0"),
    )

    order5 = Acquisition(
        datetime(2019, 1, 23, tzinfo=timezone.utc),
        isin=ISIN("X"),
        quantity=Decimal("5.0"),
        amount=Decimal("15000.0"),
    )

    order6 = Disposal(
        datetime(2019, 1, 24, tzinfo=timezone.utc),
        isin=ISIN("X"),
        quantity=Decimal("2.0"),
        amount=Decimal("8000.0"),
    )

    order7 = Acquisition(
        datetime(2019, 1, 25, tzinfo=timezone.utc),
        isin=ISIN("X"),
        quantity=Decimal("1.0"),
        amount=Decimal("3300.0"),
    )

    order8 = Disposal(
        datetime(2019, 1, 25, tzinfo=timezone.utc),
        isin=ISIN("X"),
        quantity=Decimal("1.0"),
        amount=Decimal("3500.0"),
    )

    order9 = Acquisition(
        datetime(2019, 1, 26, tzinfo=timezone.utc),
        isin=ISIN("X"),
        quantity=Decimal("4.0"),
        amount=Decimal("17000.0"),
    )

    order10 = Disposal(
        datetime(2019, 1, 27, tzinfo=timezone.utc),
        isin=ISIN("X"),
        quantity=Decimal("8.0"),
        amount=Decimal("70000.0"),
    )

    tax_calculator = make_tax_calculator(
        [
            order1,
            order2,
            order3,
            order4,
            order5,
            order6,
            order7,
            order8,
            order9,
            order10,
        ]
    )
    capital_gains = tax_calculator.capital_gains()
    assert len(capital_gains) == 5

    cg = capital_gains[0]
    assert cg.date_acquired == date(2019, 1, 18)
    assert cg.cost == Decimal("9018.75")
    assert cg.gain_loss == Decimal("81.25")

    cg = capital_gains[1]
    assert cg.date_acquired == date(2019, 1, 22)
    assert cg.cost == Decimal("2000.00")
    assert cg.gain_loss == Decimal("3000.0")

    cg = capital_gains[2]
    assert cg.date_acquired == date(2019, 1, 26)
    assert cg.cost == Decimal("8500.00")
    assert cg.gain_loss == Decimal("-500.0")

    cg = capital_gains[3]
    assert cg.date_acquired == date(2019, 1, 25)
    assert cg.cost == Decimal("3300.0")
    assert cg.gain_loss == Decimal("200.0")

    cg = capital_gains[4]
    assert cg.date_acquired is None
    assert cg.cost == Decimal("26506.25")
    assert cg.gain_loss == Decimal("43493.75")

    assert tax_calculator.holding(Ticker("X")) is None


# The following tests are based on the HMRC examples for calculating the
# capital gains or losses on the disposal of cryptoassets. The gain/loss
# is calculated in the same exact way as if the assets were shares from
# a company and not cryptoassets.


def test_hmrc_example_crypto22251(make_tax_calculator):
    """
    https://www.gov.uk/hmrc-internal-manuals/cryptoassets-manual/crypto22251
    """
    order1 = Acquisition(
        datetime(2019, 1, 1, tzinfo=timezone.utc),
        isin=ISIN("TOKEN-A"),
        quantity=Decimal("100.0"),
        amount=Decimal("1000.0"),
    )

    order2 = Acquisition(
        datetime(2020, 9, 18, tzinfo=timezone.utc),
        isin=ISIN("TOKEN-A"),
        quantity=Decimal("50.0"),
        amount=Decimal("125000.0"),
    )

    order3 = Disposal(
        datetime(2020, 12, 1, tzinfo=timezone.utc),
        isin=ISIN("TOKEN-A"),
        quantity=Decimal("50.0"),
        amount=Decimal("300000.0"),
    )

    tax_calculator = make_tax_calculator([order1, order2, order3])
    capital_gains = tax_calculator.capital_gains()
    assert len(capital_gains) == 1

    cg = capital_gains[0]
    assert cg.disposal.date == date(2020, 12, 1)
    assert cg.date_acquired is None
    assert cg.cost == Decimal("42000.0")
    assert cg.gain_loss == Decimal("258000.0")

    holding = tax_calculator.holding(ISIN("TOKEN-A"))
    assert holding.quantity == Decimal("100.0")
    assert holding.cost == Decimal("84000.0")


def test_hmrc_example_crypto22252(make_tax_calculator):
    """
    https://www.gov.uk/hmrc-internal-manuals/cryptoassets-manual/crypto22252
    """
    order1 = Acquisition(
        datetime(2019, 1, 1, tzinfo=timezone.utc),
        isin=ISIN("TOKEN-B"),
        quantity=Decimal("5000.0"),
        amount=Decimal("500.0"),
    )

    order2 = Disposal(
        datetime(2020, 6, 23, 9, 0, tzinfo=timezone.utc),
        isin=ISIN("TOKEN-B"),
        quantity=Decimal("1000.0"),
        amount=Decimal("800.0"),
    )

    order3 = Acquisition(
        datetime(2020, 6, 23, 13, 0, tzinfo=timezone.utc),
        isin=ISIN("TOKEN-B"),
        quantity=Decimal("1600.0"),
        amount=Decimal("1000.0"),
    )

    order4 = Disposal(
        datetime(2020, 6, 23, 19, 0, tzinfo=timezone.utc),
        isin=ISIN("TOKEN-B"),
        quantity=Decimal("500.0"),
        amount=Decimal("600.0"),
    )

    tax_calculator = make_tax_calculator([order1, order2, order3, order4])
    capital_gains = tax_calculator.capital_gains()
    assert len(capital_gains) == 1

    cg = capital_gains[0]
    assert cg.disposal.date == date(2020, 6, 23)
    assert cg.date_acquired == date(2020, 6, 23)
    assert cg.cost == Decimal("937.5")
    assert cg.gain_loss == Decimal("462.5")

    holding = tax_calculator.holding(ISIN("TOKEN-B"))
    assert holding.quantity == Decimal("5100.0")
    assert holding.cost == Decimal("562.5")


def test_hmrc_example_crypto22253(make_tax_calculator):
    """
    https://www.gov.uk/hmrc-internal-manuals/cryptoassets-manual/crypto22253
    """
    order1 = Acquisition(
        datetime(2019, 1, 1, tzinfo=timezone.utc),
        isin=ISIN("TOKEN-C"),
        quantity=Decimal("2000.0"),
        amount=Decimal("1000.0"),
    )

    order2 = Disposal(
        datetime(2020, 3, 31, tzinfo=timezone.utc),
        isin=ISIN("TOKEN-C"),
        quantity=Decimal("1000.0"),
        amount=Decimal("400.0"),
    )

    order3 = Disposal(
        datetime(2020, 4, 20, tzinfo=timezone.utc),
        isin=ISIN("TOKEN-C"),
        quantity=Decimal("500.0"),
        amount=Decimal("150.0"),
    )

    order4 = Acquisition(
        datetime(2020, 4, 21, tzinfo=timezone.utc),
        isin=ISIN("TOKEN-C"),
        quantity=Decimal("700.0"),
        amount=Decimal("175.0"),
    )

    order5 = Acquisition(
        datetime(2020, 4, 28, tzinfo=timezone.utc),
        isin=ISIN("TOKEN-C"),
        quantity=Decimal("500.0"),
        amount=Decimal("100.0"),
    )

    order6 = Acquisition(
        datetime(2020, 5, 1, tzinfo=timezone.utc),
        isin=ISIN("TOKEN-C"),
        quantity=Decimal("500.0"),
        amount=Decimal("150.0"),
    )

    tax_calculator = make_tax_calculator(
        [order1, order2, order3, order4, order5, order6]
    )
    capital_gains = tax_calculator.capital_gains()
    assert len(capital_gains) == 4

    cg = capital_gains[0]
    assert cg.disposal.date == date(2020, 3, 31)
    assert cg.date_acquired == date(2020, 4, 21)
    assert cg.cost == Decimal("175.0")
    assert cg.gain_loss == Decimal("105.0")

    cg = capital_gains[1]
    assert cg.disposal.date == date(2020, 3, 31)
    assert cg.date_acquired == date(2020, 4, 28)
    assert cg.cost == Decimal("60.0")
    assert cg.gain_loss == Decimal("60.0")

    cg = capital_gains[2]
    assert cg.disposal.date == date(2020, 4, 20)
    assert cg.date_acquired == date(2020, 4, 28)
    assert cg.cost == Decimal("40.0")
    assert cg.gain_loss == Decimal("20.0")

    cg = capital_gains[3]
    assert cg.disposal.date == date(2020, 4, 20)
    assert cg.date_acquired == date(2020, 5, 1)
    assert cg.cost == Decimal("90.0")
    assert cg.gain_loss == Decimal("0.0")

    holding = tax_calculator.holding(ISIN("TOKEN-C"))
    assert holding.quantity == Decimal("2200.0")
    assert holding.cost == Decimal("1060.0")


def test_hmrc_example_crypto22254(make_tax_calculator):
    """
    https://www.gov.uk/hmrc-internal-manuals/cryptoassets-manual/crypto22254
    """
    order1 = Acquisition(
        datetime(2019, 1, 1, tzinfo=timezone.utc),
        isin=ISIN("TOKEN-D"),
        quantity=Decimal("8000.0"),
        amount=Decimal("1000.0"),
    )

    order2 = Disposal(
        datetime(2020, 1, 31, tzinfo=timezone.utc),
        isin=ISIN("TOKEN-D"),
        quantity=Decimal("5000.0"),
        amount=Decimal("500.0"),
    )

    order3 = Acquisition(
        datetime(2020, 1, 31, tzinfo=timezone.utc),
        isin=ISIN("TOKEN-D"),
        quantity=Decimal("4000.0"),
        amount=Decimal("320.0"),
    )

    order4 = Acquisition(
        datetime(2020, 1, 31, tzinfo=timezone.utc),
        isin=ISIN("TOKEN-D"),
        quantity=Decimal("1000.0"),
        amount=Decimal("75.0"),
    )

    order5 = Acquisition(
        datetime(2020, 1, 31, tzinfo=timezone.utc),
        isin=ISIN("TOKEN-D"),
        quantity=Decimal("1000.0"),
        amount=Decimal("70.0"),
    )

    order6 = Disposal(
        datetime(2020, 1, 31, tzinfo=timezone.utc),
        isin=ISIN("TOKEN-D"),
        quantity=Decimal("2000.0"),
        amount=Decimal("142.0"),
    )

    order7 = Acquisition(
        datetime(2020, 1, 31, tzinfo=timezone.utc),
        isin=ISIN("TOKEN-D"),
        quantity=Decimal("500.0"),
        amount=Decimal("35.0"),
    )

    tax_calculator = make_tax_calculator(
        [order1, order2, order3, order4, order5, order6, order7]
    )
    capital_gains = tax_calculator.capital_gains()
    assert len(capital_gains) == 2

    cg = capital_gains[0]
    assert cg.disposal.date == date(2020, 1, 31)
    assert cg.date_acquired == date(2020, 1, 31)
    assert cg.cost == Decimal("500.0")
    assert cg.gain_loss.quantize(Decimal("0.00")) == Decimal("96.14")

    cg = capital_gains[1]
    assert cg.disposal.date == date(2020, 1, 31)
    assert cg.date_acquired is None
    assert cg.cost == Decimal("62.5")
    assert cg.gain_loss.quantize(Decimal("0.00")) == Decimal("-16.64")

    holding = tax_calculator.holding(ISIN("TOKEN-D"))
    assert holding.quantity == Decimal("7500.0")
    assert holding.cost == Decimal("937.5")


def test_hmrc_example_crypto22255(make_tax_calculator):
    """
    https://www.gov.uk/hmrc-internal-manuals/cryptoassets-manual/crypto22255
    """
    order1 = Acquisition(
        datetime(2019, 1, 1, tzinfo=timezone.utc),
        isin=ISIN("TOKEN-E"),
        quantity=Decimal("14000.0"),
        amount=Decimal("200000.0"),
    )

    order2 = Disposal(
        datetime(2020, 8, 30, tzinfo=timezone.utc),
        isin=ISIN("TOKEN-E"),
        quantity=Decimal("4000.0"),
        amount=Decimal("160000.0"),
    )

    order3 = Acquisition(
        datetime(2020, 9, 11, tzinfo=timezone.utc),
        isin=ISIN("TOKEN-E"),
        quantity=Decimal("500.0"),
        amount=Decimal("17500.0"),
    )

    tax_calculator = make_tax_calculator([order1, order2, order3])
    capital_gains = tax_calculator.capital_gains()
    assert len(capital_gains) == 2

    cg = capital_gains[0]
    assert cg.disposal.date == date(2020, 8, 30)
    assert cg.date_acquired == date(2020, 9, 11)
    assert cg.cost == Decimal("17500.0")
    assert cg.gain_loss == Decimal("2500.0")

    cg = capital_gains[1]
    assert cg.disposal.date == date(2020, 8, 30)
    assert cg.date_acquired is None
    assert cg.cost == Decimal("50000.0")
    assert cg.gain_loss == Decimal("90000.0")

    holding = tax_calculator.holding(ISIN("TOKEN-E"))
    assert holding.quantity == Decimal("10500.0")
    assert holding.cost == Decimal("150000.0")


def test_hmrc_example_crypto22256(make_tax_calculator):
    """
    https://www.gov.uk/hmrc-internal-manuals/cryptoassets-manual/crypto22256
    """
    order1 = Acquisition(
        datetime(2019, 1, 1, tzinfo=timezone.utc),
        isin=ISIN("TOKEN-F"),
        quantity=Decimal("100000.0"),
        amount=Decimal("300000.0"),
    )

    order2 = Acquisition(
        datetime(2020, 7, 31, tzinfo=timezone.utc),
        isin=ISIN("TOKEN-F"),
        quantity=Decimal("10000.0"),
        amount=Decimal("45000.0"),
    )

    order3 = Disposal(
        datetime(2020, 7, 31, tzinfo=timezone.utc),
        isin=ISIN("TOKEN-F"),
        quantity=Decimal("30000.0"),
        amount=Decimal("150000.0"),
    )

    order4 = Disposal(
        datetime(2020, 8, 5, tzinfo=timezone.utc),
        isin=ISIN("TOKEN-F"),
        quantity=Decimal("20000.0"),
        amount=Decimal("100000.0"),
    )

    order5 = Acquisition(
        datetime(2020, 8, 6, tzinfo=timezone.utc),
        isin=ISIN("TOKEN-F"),
        quantity=Decimal("50000.0"),
        amount=Decimal("225000.0"),
    )

    order6 = Disposal(
        datetime(2020, 8, 7, tzinfo=timezone.utc),
        isin=ISIN("TOKEN-F"),
        quantity=Decimal("100000.0"),
        amount=Decimal("150000.0"),
    )

    tax_calculator = make_tax_calculator(
        [order1, order2, order3, order4, order5, order6]
    )
    capital_gains = tax_calculator.capital_gains()
    assert len(capital_gains) == 4

    cg = capital_gains[0]
    assert cg.disposal.date == date(2020, 7, 31)
    assert cg.date_acquired == date(2020, 7, 31)
    assert cg.cost == Decimal("45000.0")
    assert cg.gain_loss == Decimal("5000.0")

    cg = capital_gains[1]
    assert cg.disposal.date == date(2020, 7, 31)
    assert cg.date_acquired == date(2020, 8, 6)
    assert cg.cost == Decimal("90000.0")
    assert cg.gain_loss == Decimal("10000.0")

    cg = capital_gains[2]
    assert cg.disposal.date == date(2020, 8, 5)
    assert cg.date_acquired == date(2020, 8, 6)
    assert cg.cost == Decimal("90000.0")
    assert cg.gain_loss == Decimal("10000.0")

    cg = capital_gains[3]
    assert cg.disposal.date == date(2020, 8, 7)
    assert cg.date_acquired is None
    assert cg.cost.quantize(Decimal("0.00")) == Decimal("313636.36")
    assert cg.gain_loss.quantize(Decimal("0.00")) == Decimal("-163636.36")

    holding = tax_calculator.holding(ISIN("TOKEN-F"))
    assert holding.quantity == Decimal("10000.0")
    assert holding.cost.quantize(Decimal("0.00")) == Decimal("31363.64")


def test_show_holdings_with_gain_loss(make_tax_calculator, capsys):
    order = Acquisition(
        datetime(2019, 1, 18, tzinfo=timezone.utc),
        isin=ISIN("X"),
        ticker="TICKER",
        quantity=Decimal("10.0"),
        amount=Decimal("100.0"),
    )

    tax_calculator = make_tax_calculator(
        [order], price=Price(Decimal("15.0"), Currency.GBP)
    )
    tax_calculator.show_holdings(show_gain_loss=True)

    captured = capsys.readouterr()
    assert "Unrealised Gain/Loss (£)" in captured.out
    assert "50.00" in captured.out


def test_show_holdings_with_gain_loss_and_currency_conversion(
    make_tax_calculator, capsys
):
    order = Acquisition(
        datetime(2019, 1, 18, tzinfo=timezone.utc),
        isin=ISIN("X"),
        ticker="TICKER",
        quantity=Decimal("10.0"),
        amount=Decimal("100.0"),
    )

    tax_calculator = make_tax_calculator(
        [order],
        price=Price(Decimal("15.0"), Currency.USD),
        fx_rate=Decimal("0.75"),
    )
    tax_calculator.show_holdings(show_gain_loss=True)

    captured = capsys.readouterr()
    assert "Unrealised Gain/Loss (£)" in captured.out
    assert "12.50" in captured.out


def test_show_holdings_with_gain_loss_when_price_or_fx_rate_not_available(
    make_tax_calculator, capsys
):
    order = Acquisition(
        datetime(2019, 1, 18, tzinfo=timezone.utc),
        isin=ISIN("X"),
        ticker="TICKER",
        quantity=Decimal("10.0"),
        amount=Decimal("100.0"),
    )

    tax_calculator = make_tax_calculator([order], price=DataProviderError)
    tax_calculator.show_holdings(show_gain_loss=True)

    captured = capsys.readouterr()
    assert "Unrealised Gain/Loss (£)" in captured.out
    assert "Not available" in captured.out

    tax_calculator = make_tax_calculator(
        [order],
        price=Price(Decimal("15.0"), Currency.USD),
        fx_rate=DataProviderError,
    )

    tax_calculator.show_holdings(show_gain_loss=True)
    captured = capsys.readouterr()
    assert "Unrealised Gain/Loss (£)" in captured.out
    assert "Not available" in captured.out


def test_show_holdings_ambiguous_ticker(make_tax_calculator, capsys):
    order1 = Acquisition(
        datetime(2019, 1, 18, tzinfo=timezone.utc),
        isin=ISIN("X"),
        ticker="TICKER",
        quantity=Decimal("10.0"),
        amount=Decimal("100.0"),
    )

    order2 = Acquisition(
        datetime(2019, 1, 20, tzinfo=timezone.utc),
        isin=ISIN("Y"),
        ticker="TICKER",
        quantity=Decimal("5.0"),
        amount=Decimal("150.0"),
    )

    tax_calculator = make_tax_calculator([order1, order2])
    tax_calculator.show_holdings(ticker_filter=Ticker("TICKER"))

    captured = capsys.readouterr()
    assert not captured.out
    assert not captured.err
