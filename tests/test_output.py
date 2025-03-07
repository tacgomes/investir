from datetime import datetime, timezone
from decimal import Decimal

from investir.findata import FinancialData
from investir.output import OutputGenerator
from investir.prettytable import OutputFormat
from investir.taxcalculator import TaxCalculator
from investir.transaction import (
    Acquisition,
)
from investir.trhistory import TransactionHistory
from investir.typing import ISIN, Ticker
from investir.utils import sterling

# NB: Most of the output generated by the output module is already
# tested on test_cli.py.


def test_create_holdings_table_ambiguous_ticker(capsys):
    order1 = Acquisition(
        datetime(2019, 1, 18, tzinfo=timezone.utc),
        isin=ISIN("X"),
        ticker="TICKER",
        total=sterling("100.0"),
        quantity=Decimal("10.0"),
    )

    order2 = Acquisition(
        datetime(2019, 1, 20, tzinfo=timezone.utc),
        isin=ISIN("Y"),
        ticker="TICKER",
        total=sterling("150.0"),
        quantity=Decimal("5.0"),
    )

    trhistory = TransactionHistory(orders=[order1, order2])
    findata = FinancialData(None, None, None)
    taxcalc = TaxCalculator(trhistory, findata)

    outputter = OutputGenerator(trhistory, taxcalc)
    outputter.show_holdings(format=OutputFormat.TEXT, ticker_filter=Ticker("TICKER"))
    captured = capsys.readouterr()

    assert not captured.out
    assert not captured.err
