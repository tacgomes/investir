from datetime import datetime, date, timedelta
from decimal import Decimal

import pytest

from investir.taxcalculator import TaxCalculator
from investir.transaction import Acquisition, Disposal
from investir.trhistory import TrHistory


def test_section_104_disposal():
    """
    Test Section 104 disposals using HMRC example:
      https://assets.publishing.service.gov.uk/media/65f993439316f5001164c2d7/HS284_Example_3_2024.pdf
    """
    order1 = Acquisition(
        datetime(2015, 4, 1),
        ticker="LOBS",
        quantity=Decimal("1000.0"),
        amount=Decimal("4000.0"),
        fees=Decimal("150.0"),
    )

    order2 = Acquisition(
        datetime(2018, 9, 1),
        ticker="LOBS",
        quantity=Decimal("500.0"),
        amount=Decimal("2050.0"),
        fees=Decimal("80.0"),
    )

    order3 = Disposal(
        datetime(2023, 5, 1),
        ticker="LOBS",
        quantity=Decimal("700.0"),
        amount=Decimal("3360.0"),
        fees=Decimal("100.0"),
    )

    order4 = Disposal(
        datetime(2024, 2, 1),
        ticker="LOBS",
        quantity=Decimal("400.0"),
        amount=Decimal("2080.0"),
        fees=Decimal("105.0"),
    )

    tr_hist = TrHistory()
    tr_hist.insert_orders([order1, order2, order3, order4])

    tax_calculator = TaxCalculator(tr_hist)
    capital_gains = tax_calculator.capital_gains()
    assert len(capital_gains) == 2
    assert capital_gains == tax_calculator.capital_gains(2023)

    cg = capital_gains[0]
    assert cg.disposal.date == date(2023, 5, 1)
    assert cg.date_acquired is None
    assert cg.cost.quantize(Decimal("0.00")) == Decimal("3030.67")
    assert cg.gain_loss.quantize(Decimal("0.00")) == Decimal("329.33")

    cg = capital_gains[1]
    assert cg.disposal.date == date(2024, 2, 1)
    assert cg.date_acquired is None
    assert cg.cost.quantize(Decimal("0.00")) == Decimal("1779.67")
    assert cg.gain_loss.quantize(Decimal("0.00")) == Decimal("300.33")

    holding = tax_calculator.holdings()["LOBS"]
    assert holding.quantity == Decimal("400.0")
    assert holding.cost.quantize(Decimal("0.00")) == Decimal("1674.67")


def test_section_104_with_no_disposal_made():
    order1 = Acquisition(
        datetime(2015, 4, 1),
        ticker="X",
        quantity=Decimal("1000.0"),
        amount=Decimal("4000.0"),
        fees=Decimal("150.0"),
    )

    order2 = Acquisition(
        datetime(2018, 9, 1),
        ticker="X",
        quantity=Decimal("500.0"),
        amount=Decimal("2000.0"),
        fees=Decimal("50.0"),
    )

    tr_hist = TrHistory()
    tr_hist.insert_orders([order1, order2])

    tax_calculator = TaxCalculator(tr_hist)

    holding = tax_calculator.holdings()["X"]
    assert holding.quantity == Decimal("1500.0")
    assert holding.cost == Decimal("6200.0")


def test_same_day_rule():
    order1 = Acquisition(
        datetime(2018, 1, 1),
        ticker="X",
        quantity=Decimal("10.0"),
        amount=Decimal("100.0"),
    )

    order2 = Disposal(
        datetime(2019, 1, 20, 14, 00),
        ticker="X",
        quantity=Decimal("1.0"),
        amount=Decimal("70.0"),
    )

    order3 = Acquisition(
        datetime(2019, 1, 20, 15, 00),
        ticker="X",
        quantity=Decimal("1.0"),
        amount=Decimal("60.0"),
    )

    order4 = Acquisition(
        datetime(2019, 1, 20, 16, 00),
        ticker="X",
        quantity=Decimal("2.0"),
        amount=Decimal("65.0"),
    )

    order5 = Disposal(
        datetime(2019, 1, 20, 17, 00),
        ticker="X",
        quantity=Decimal("4.0"),
        amount=Decimal("280.0"),
    )

    order6 = Acquisition(
        datetime(2019, 1, 20, 18, 00),
        ticker="X",
        quantity=Decimal("2.0"),
        amount=Decimal("55.0"),
    )

    tr_hist = TrHistory()
    tr_hist.insert_orders([order1, order2, order3, order4, order5, order6])

    tax_calculator = TaxCalculator(tr_hist)
    capital_gains = tax_calculator.capital_gains()
    assert len(capital_gains) == 1

    cg = capital_gains[0]
    assert cg.date_acquired == date(2019, 1, 20)
    assert cg.disposal.amount == order2.amount + order5.amount
    assert cg.cost == order3.amount + order4.amount + order6.amount
    assert cg.gain_loss == Decimal("170.00")

    holding = tax_calculator.holdings()["X"]
    assert holding.quantity == Decimal("10.0")
    assert holding.cost == Decimal("100.0")


@pytest.mark.parametrize("days_elapsed", range(1, 31))
def test_bed_and_breakfast_rule(days_elapsed):
    order1 = Acquisition(
        datetime(2019, 1, 18),
        ticker="X",
        quantity=Decimal("10.0"),
        amount=Decimal("100.0"),
    )

    order2 = Disposal(
        datetime(2019, 1, 20),
        ticker="X",
        quantity=Decimal("5.0"),
        amount=Decimal("150.0"),
    )

    order3 = Acquisition(
        order2.timestamp + timedelta(days=days_elapsed),
        ticker="X",
        quantity=Decimal("5.0"),
        amount=Decimal("120.0"),
    )

    tr_hist = TrHistory()
    tr_hist.insert_orders([order1, order2, order3])

    tax_calculator = TaxCalculator(tr_hist)
    capital_gains = tax_calculator.capital_gains()
    assert len(capital_gains) == 1

    cg = capital_gains[0]
    assert cg.date_acquired == order2.date + timedelta(days=days_elapsed)
    assert cg.cost == Decimal("120.0")
    assert cg.gain_loss == Decimal("30.0")

    holding = tax_calculator.holdings()["X"]
    assert holding.quantity == Decimal("10")
    assert holding.cost == Decimal("100.0")


def test_acquisitions_are_not_matched_after_thirty_days_of_disposal_date():
    order1 = Acquisition(
        datetime(2018, 1, 1),
        ticker="X",
        quantity=Decimal("10.0"),
        amount=Decimal("100.0"),
    )

    order2 = Disposal(
        datetime(2019, 1, 19),
        ticker="X",
        quantity=Decimal("5.0"),
        amount=Decimal("150.0"),
    )

    order3 = Acquisition(
        datetime(2019, 2, 19),
        ticker="X",
        quantity=Decimal("5.0"),
        amount=Decimal("120.0"),
    )

    tr_hist = TrHistory()
    tr_hist.insert_orders([order1, order2, order3])

    tax_calculator = TaxCalculator(tr_hist)
    capital_gains = tax_calculator.capital_gains()
    assert len(capital_gains) == 1

    cg = capital_gains[0]
    assert cg.date_acquired is None
    assert cg.cost == Decimal("50.0")
    assert cg.gain_loss == Decimal("100.0")

    holding = tax_calculator.holdings()["X"]
    assert holding.quantity == Decimal("10")
    assert holding.cost == Decimal("170.0")


def test_acquisitions_are_not_matched_before_disposal_date():
    order1 = Acquisition(
        datetime(2018, 1, 1),
        ticker="X",
        quantity=Decimal("10.0"),
        amount=Decimal("100.0"),
    )

    order2 = Acquisition(
        datetime(2019, 2, 18),
        ticker="X",
        quantity=Decimal("5.0"),
        amount=Decimal("200.0"),
    )

    order3 = Disposal(
        datetime(2019, 2, 19),
        ticker="X",
        quantity=Decimal("5.0"),
        amount=Decimal("150.0"),
    )

    tr_hist = TrHistory()
    tr_hist.insert_orders([order1, order2, order3])

    tax_calculator = TaxCalculator(tr_hist)
    capital_gains = tax_calculator.capital_gains()
    assert len(capital_gains) == 1

    cg = capital_gains[0]
    assert cg.date_acquired is None
    assert cg.cost == Decimal("100.00")
    assert cg.gain_loss == Decimal("50.0")

    holding = tax_calculator.holdings()["X"]
    assert holding.quantity == Decimal("10")
    assert holding.cost == Decimal("200.0")


def test_same_day_rule_has_priority_to_bed_and_breakfast_rule():
    """
    Verify that the same day rule has priority over the
    bed and breakfast rule. Note that in the list of
    tax events the bed and breakfast disposal is shown
    first due the earlier disposal date.
    """
    order1 = Acquisition(
        datetime(2018, 1, 1),
        ticker="X",
        quantity=Decimal("10.0"),
        amount=Decimal("100.0"),
    )

    order2 = Disposal(
        datetime(2019, 1, 20),
        ticker="X",
        quantity=Decimal("5.0"),
        amount=Decimal("150.0"),
    )

    order3 = Acquisition(
        datetime(2019, 1, 25),
        ticker="X",
        quantity=Decimal("5.0"),
        amount=Decimal("150.0"),
    )

    order4 = Disposal(
        datetime(2019, 1, 25),
        ticker="X",
        quantity=Decimal("5.0"),
        amount=Decimal("170.0"),
    )

    order5 = Acquisition(
        datetime(2019, 1, 27),
        ticker="X",
        quantity=Decimal("5.0"),
        amount=Decimal("300.0"),
    )

    tr_hist = TrHistory()
    tr_hist.insert_orders([order1, order2, order3, order4, order5])

    tax_calculator = TaxCalculator(tr_hist)
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

    holding = tax_calculator.holdings()["X"]
    assert holding.quantity == Decimal("10.0")
    assert holding.cost == Decimal("100.0")


def test_matching_disposals_with_larger_acquisition():
    """
    Test splitting an acquisition in two to match the first disposal,
    and then using the remaining part to match the second disposal.
    """
    order1 = Acquisition(
        datetime(2018, 1, 1),
        ticker="X",
        quantity=Decimal("10.0"),
        amount=Decimal("100.0"),
    )

    order2 = Disposal(
        datetime(2019, 1, 20),
        ticker="X",
        quantity=Decimal("5.0"),
        amount=Decimal("60.0"),
    )

    order3 = Disposal(
        datetime(2019, 1, 21),
        ticker="X",
        quantity=Decimal("1.0"),
        amount=Decimal("11.0"),
    )

    order4 = Acquisition(
        datetime(2019, 1, 22),
        ticker="X",
        quantity=Decimal("7.0"),
        amount=Decimal("70.0"),
    )

    tr_hist = TrHistory()
    tr_hist.insert_orders([order1, order2, order3, order4])

    tax_calculator = TaxCalculator(tr_hist)
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

    holding = tax_calculator.holdings()["X"]
    assert holding.quantity == Decimal("11.0")
    assert holding.cost == Decimal("110.0")


def test_matching_disposal_with_multiple_smaller_acquisitions():
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
        datetime(2018, 1, 1),
        ticker="X",
        quantity=Decimal("10.0"),
        amount=Decimal("30.0"),
    )

    order2 = Disposal(
        datetime(2019, 1, 20),
        ticker="X",
        quantity=Decimal("5.0"),
        amount=Decimal("50.0"),
    )

    order3 = Acquisition(
        datetime(2019, 1, 20),
        ticker="X",
        quantity=Decimal("1.0"),
        amount=Decimal("9.0"),
    )

    order4 = Acquisition(
        datetime(2019, 1, 25),
        ticker="X",
        quantity=Decimal("2.0"),
        amount=Decimal("16.0"),
    )

    order5 = Acquisition(
        datetime(2019, 1, 27),
        ticker="X",
        quantity=Decimal("1.0"),
        amount=Decimal("5.0"),
    )

    order6 = Disposal(
        datetime(2019, 3, 1), ticker="X", quantity=Decimal("1.0"), amount=Decimal("7.0")
    )

    tr_hist = TrHistory()
    tr_hist.insert_orders([order1, order2, order3, order4, order5, order6])

    tax_calculator = TaxCalculator(tr_hist)
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

    holding = tax_calculator.holdings()["X"]
    assert holding.quantity == Decimal("8.0")
    assert holding.cost == Decimal("24.0")


def test_capital_gains_on_orders_with_fees_included():
    order1 = Acquisition(
        datetime(2018, 1, 1),
        ticker="X",
        quantity=Decimal("10.0"),
        amount=Decimal("30.0"),
        fees=Decimal("1.5"),
    )

    order2 = Acquisition(
        datetime(2019, 1, 20),
        ticker="X",
        quantity=Decimal("5.0"),
        amount=Decimal("40.0"),
        fees=Decimal("0.5"),
    )

    order3 = Disposal(
        datetime(2019, 1, 20),
        ticker="X",
        quantity=Decimal("5.0"),
        amount=Decimal("50.0"),
        fees=Decimal("0.4"),
    )

    order4 = Disposal(
        datetime(2019, 3, 1),
        ticker="X",
        quantity=Decimal("5.0"),
        amount=Decimal("50.0"),
        fees=Decimal("0.8"),
    )

    tr_hist = TrHistory()
    tr_hist.insert_orders([order1, order2, order3, order4])

    tax_calculator = TaxCalculator(tr_hist)
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
    holding = tax_calculator.holdings()["X"]
    assert holding.quantity == Decimal("5.0")
    assert holding.cost == Decimal("15.75")


def test_disposals_on_different_tickers():
    order1 = Acquisition(
        datetime(2018, 1, 1),
        ticker="X",
        quantity=Decimal("10.0"),
        amount=Decimal("100.0"),
    )

    order2 = Acquisition(
        datetime(2018, 1, 1),
        ticker="Y",
        quantity=Decimal("20.0"),
        amount=Decimal("200.0"),
    )

    order3 = Disposal(
        datetime(2019, 1, 20),
        ticker="X",
        quantity=Decimal("1.0"),
        amount=Decimal("11.0"),
    )

    order4 = Disposal(
        datetime(2019, 1, 21),
        ticker="Y",
        quantity=Decimal("2.0"),
        amount=Decimal("22.0"),
    )

    order5 = Acquisition(
        datetime(2019, 1, 21),
        ticker="X",
        quantity=Decimal("2.0"),
        amount=Decimal("8.0"),
    )

    order6 = Acquisition(
        datetime(2019, 1, 22),
        ticker="Y",
        quantity=Decimal("2.0"),
        amount=Decimal("6.0"),
    )

    tr_hist = TrHistory()
    tr_hist.insert_orders([order1, order2, order3, order4, order5, order6])

    tax_calculator = TaxCalculator(tr_hist)
    capital_gains = tax_calculator.capital_gains()
    assert len(capital_gains) == 2

    cg = capital_gains[0]
    assert cg.date_acquired == date(2019, 1, 21)
    assert cg.disposal.ticker == "X"
    assert cg.cost == Decimal("4.0")
    assert cg.gain_loss == Decimal("7.0")

    cg = capital_gains[1]
    assert cg.date_acquired == date(2019, 1, 22)
    assert cg.disposal.ticker == "Y"
    assert cg.cost == Decimal("6.0")
    assert cg.gain_loss == Decimal("16.0")

    holding = tax_calculator.holdings()["X"]
    assert holding.quantity == Decimal("11.0")
    assert holding.cost == Decimal("104.0")

    holding = tax_calculator.holdings()["Y"]
    assert holding.quantity == Decimal("20.0")
    assert holding.cost == Decimal("200.0")


def test_integrity_disposal_without_acquisition():
    order = Disposal(
        datetime(2019, 1, 17),
        ticker="X",
        quantity=Decimal("5.0"),
        amount=Decimal("120.0"),
    )

    tr_hist = TrHistory()
    tr_hist.insert_orders([order])

    with pytest.raises(RuntimeError):
        TaxCalculator(tr_hist)


def test_integrity_disposing_more_than_quantity_acquired():
    order1 = Acquisition(
        datetime(2019, 1, 18),
        ticker="X",
        quantity=Decimal("5.0"),
        amount=Decimal("100.0"),
    )

    order2 = Disposal(
        datetime(2019, 3, 17),
        ticker="X",
        quantity=Decimal("10.0"),
        amount=Decimal("120.0"),
    )

    tr_hist = TrHistory()
    tr_hist.insert_orders([order1, order2])

    with pytest.raises(RuntimeError):
        TaxCalculator(tr_hist)


def test_rppaccounts_example():
    """
    Rawlinson Pryde & Partners Accountants full example:
      https://rppaccounts.co.uk/taxation-of-shares/
    """
    order1 = Acquisition(
        datetime(2019, 1, 18),
        ticker="X",
        quantity=Decimal("4.0"),
        amount=Decimal("12025.0"),
    )

    order2 = Disposal(
        datetime(2019, 1, 18),
        ticker="X",
        quantity=Decimal("3.0"),
        amount=Decimal("9100.0"),
    )

    order3 = Disposal(
        datetime(2019, 1, 19),
        ticker="X",
        quantity=Decimal("1.0"),
        amount=Decimal("5000.0"),
    )

    order4 = Acquisition(
        datetime(2019, 1, 22),
        ticker="X",
        quantity=Decimal("1.0"),
        amount=Decimal("2000.0"),
    )

    order5 = Acquisition(
        datetime(2019, 1, 23),
        ticker="X",
        quantity=Decimal("5.0"),
        amount=Decimal("15000.0"),
    )

    order6 = Disposal(
        datetime(2019, 1, 24),
        ticker="X",
        quantity=Decimal("2.0"),
        amount=Decimal("8000.0"),
    )

    order7 = Acquisition(
        datetime(2019, 1, 25),
        ticker="X",
        quantity=Decimal("1.0"),
        amount=Decimal("3300.0"),
    )

    order8 = Disposal(
        datetime(2019, 1, 25),
        ticker="X",
        quantity=Decimal("1.0"),
        amount=Decimal("3500.0"),
    )

    order9 = Acquisition(
        datetime(2019, 1, 26),
        ticker="X",
        quantity=Decimal("4.0"),
        amount=Decimal("17000.0"),
    )

    order10 = Disposal(
        datetime(2019, 1, 27),
        ticker="X",
        quantity=Decimal("8.0"),
        amount=Decimal("70000.0"),
    )

    tr_hist = TrHistory()
    tr_hist.insert_orders(
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

    tax_calculator = TaxCalculator(tr_hist)
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

    assert "X" not in tax_calculator.holdings()
