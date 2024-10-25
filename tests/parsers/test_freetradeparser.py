import csv
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from decimal import Decimal
from typing import Final

import pytest

from investir.config import config
from investir.exceptions import (
    CalculatedAmountError,
    CurrencyError,
    FeesError,
    OrderDateError,
    TransactionTypeError,
)
from investir.parser.freetrade import FreetradeParser
from investir.transaction import Acquisition, Disposal
from investir.typing import ISIN, Ticker

TIMESTAMP: Final = datetime(2021, 7, 26, 7, 41, 32, 582, tzinfo=timezone.utc)

ACQUISITION: Final = {
    "Title": "Amazon",
    "Type": "ORDER",
    "Timestamp": TIMESTAMP,
    "Account Currency": "GBP",
    "Total Amount": "1330.20",
    "Buy / Sell": "BUY",
    "Ticker": "AMZN",
    "ISIN": "AMZN-ISIN",
    "Price per Share in Account Currency": "132.5",
    "Stamp Duty": "5.2",
    "Quantity": "10.0",
}

DISPOSAL: Final = {
    "Title": "Skyworks",
    "Type": "ORDER",
    "Timestamp": TIMESTAMP,
    "Account Currency": "GBP",
    "Total Amount": "1111.85",
    "Buy / Sell": "SELL",
    "Ticker": "SWKS",
    "ISIN": "SWKS-ISIN",
    "Price per Share in Account Currency": "532.5",
    "Quantity": "2.1",
    "FX Fee Amount": "6.4",
}

DIVIDEND: Final = {
    "Title": "Skyworks",
    "Type": "DIVIDEND",
    "Timestamp": TIMESTAMP,
    "Account Currency": "GBP",
    "Total Amount": "2.47",
    "Ticker": "SWKS",
    "ISIN": "SWKS-ISIN",
    "Base FX Rate": "0.75440000",
    "Dividend Eligible Quantity": "6.88764135",
    "Dividend Amount Per Share": "0.56000000",
    "Dividend Withheld Tax Percentage": "15",
    "Dividend Withheld Tax Amount": "0.58",
}


@pytest.fixture(name="create_parser")
def fixture_create_parser(tmp_path) -> Callable:
    config.include_fx_fees = True

    def _create_parser(rows: Sequence[Mapping[str, str]]) -> FreetradeParser:
        csv_file = tmp_path / "transactions.csv"
        with csv_file.open("w", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=FreetradeParser.FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        return FreetradeParser(csv_file)

    return _create_parser


@pytest.fixture(name="create_parser_format_unrecognised")
def fixture_create_parser_format_unrecognised(tmp_path) -> FreetradeParser:
    csv_file = tmp_path / "transactions.csv"
    with csv_file.open("w", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=("Field1", "Field2"))
        writer.writeheader()
        writer.writerow(
            {
                "Field1": "A",
                "Field2": "B",
            }
        )
    return FreetradeParser(csv_file)


def test_parser_happy_path(create_parser):
    acquisition = ACQUISITION
    disposal = DISPOSAL
    dividend = DIVIDEND

    deposit = {
        "Type": "TOP_UP",
        "Timestamp": TIMESTAMP,
        "Account Currency": "GBP",
        "Total Amount": "1000.00",
    }

    withdrawal = {
        "Type": "WITHDRAWAL",
        "Timestamp": TIMESTAMP,
        "Account Currency": "GBP",
        "Total Amount": "500.25",
    }

    interest = {
        "Type": "INTEREST_FROM_CASH",
        "Timestamp": TIMESTAMP,
        "Account Currency": "GBP",
        "Total Amount": "4.65",
    }

    statement = {"Type": "MONTHLY_STATEMENT"}

    parser = create_parser(
        [
            acquisition,
            disposal,
            dividend,
            deposit,
            withdrawal,
            interest,
            statement,
        ]
    )

    assert parser.can_parse()

    parser_result = parser.parse()
    assert len(parser_result.orders) == 2

    order = parser_result.orders[0]
    assert isinstance(order, Disposal)
    assert order.timestamp == TIMESTAMP
    assert order.isin == ISIN("SWKS-ISIN")
    assert order.ticker == Ticker("SWKS")
    assert order.name == "Skyworks"
    assert order.amount == Decimal("1118.25")
    assert order.quantity == Decimal("2.1")
    assert order.fees == Decimal("6.4")

    order = parser_result.orders[1]
    assert isinstance(order, Acquisition)
    assert order.timestamp == TIMESTAMP
    assert order.isin == ISIN("AMZN-ISIN")
    assert order.ticker == Ticker("AMZN")
    assert order.name == "Amazon"
    assert order.amount == Decimal("1325.00")
    assert order.quantity == Decimal("10")
    assert order.fees == Decimal("5.2")

    assert len(parser_result.dividends) == 1
    dividend = parser_result.dividends[0]

    assert dividend.timestamp == TIMESTAMP
    assert dividend.isin == ISIN("SWKS-ISIN")
    assert dividend.name == "Skyworks"
    assert dividend.ticker == Ticker("SWKS")
    assert dividend.amount == Decimal("2.47")
    assert dividend.withheld == Decimal("0.4375520000")

    assert len(parser_result.transfers) == 2

    transfer = parser_result.transfers[0]
    assert transfer.timestamp == TIMESTAMP
    assert transfer.amount == Decimal("-500.25")

    transfer = parser_result.transfers[1]
    assert transfer.timestamp == TIMESTAMP
    assert transfer.amount == Decimal("1000.00")

    assert len(parser_result.interest) == 1
    interest = parser_result.interest[0]
    assert interest.timestamp == TIMESTAMP
    assert interest.amount == Decimal("4.65")


def test_parser_when_fx_fees_are_not_allowable_cost(create_parser):
    config.include_fx_fees = False

    order1 = dict(ACQUISITION)
    order1["Timestamp"] = TIMESTAMP
    order1["FX Fee Amount"] = "5.2"
    del order1["Stamp Duty"]

    order2 = dict(DISPOSAL)
    order2["Timestamp"] = TIMESTAMP

    order3 = {
        "Title": "Microsoft",
        "Type": "ORDER",
        "Timestamp": TIMESTAMP,
        "Account Currency": "GBP",
        "Total Amount": "1326.30",
        "Buy / Sell": "BUY",
        "Ticker": "MSFT",
        "ISIN": "MSFT-ISIN",
        "Price per Share in Account Currency": "132.5",
        "Stamp Duty": "1.3",
        "Quantity": "10.0",
        "FX Fee Amount": "",
    }

    parser = create_parser([order1, order2, order3])

    parser_result = parser.parse()
    assert len(parser_result.orders) == 3

    order = parser_result.orders[0]
    assert isinstance(order, Acquisition)
    assert order.timestamp == TIMESTAMP
    assert order.isin == ISIN("MSFT-ISIN")
    assert order.ticker == Ticker("MSFT")
    assert order.name == "Microsoft"
    assert order.amount == Decimal("1325.00")
    assert order.quantity == Decimal("10.0")
    assert order.fees == Decimal("1.3")

    order = parser_result.orders[1]
    assert isinstance(order, Disposal)
    assert order.timestamp == TIMESTAMP
    assert order.isin == ISIN("SWKS-ISIN")
    assert order.ticker == Ticker("SWKS")
    assert order.name == "Skyworks"
    assert order.amount == Decimal("1118.25")
    assert order.quantity == Decimal("2.1")
    assert order.fees == Decimal("0.0")

    order = parser_result.orders[2]
    assert isinstance(order, Acquisition)
    assert order.timestamp == TIMESTAMP
    assert order.isin == ISIN("AMZN-ISIN")
    assert order.ticker == Ticker("AMZN")
    assert order.name == "Amazon"
    assert order.amount == Decimal("1325.00")
    assert order.quantity == Decimal("10")
    assert order.fees == Decimal("0.0")


def test_parser_cannot_parse(create_parser_format_unrecognised):
    parser = create_parser_format_unrecognised
    assert parser.can_parse() is False


def test_parser_invalid_transaction_type(create_parser):
    order = dict(ACQUISITION)
    order["Type"] = "NOT-VALID"
    parser = create_parser([order])
    assert parser.can_parse()
    with pytest.raises(TransactionTypeError):
        parser.parse()


def test_parser_invalid_buy_sell(create_parser):
    order = dict(ACQUISITION)
    order["Buy / Sell"] = "NOT-VALID"
    parser = create_parser([order])
    assert parser.can_parse()
    with pytest.raises(TransactionTypeError):
        parser.parse()


def test_parser_invalid_account_currency(create_parser):
    order = dict(ACQUISITION)
    order["Account Currency"] = "USD"
    parser = create_parser([order])
    assert parser.can_parse()
    with pytest.raises(CurrencyError):
        parser.parse()


def test_parser_stamp_duty_and_fx_fee_non_zero(create_parser):
    order = dict(ACQUISITION)
    order["FX Fee Amount"] = "1.2"
    parser = create_parser([order])
    assert parser.can_parse()
    with pytest.raises(FeesError):
        parser.parse()


def test_parser_order_too_old(create_parser):
    order = dict(ACQUISITION)
    order["Timestamp"] = "2008-04-05T09:00:00.000Z"
    parser = create_parser([order])
    assert parser.can_parse()
    with pytest.raises(OrderDateError):
        parser.parse()


def test_parser_order_calculated_amount_mismatch(create_parser):
    order = dict(ACQUISITION)
    order["Total Amount"] = "7.5"
    parser = create_parser([order])
    assert parser.can_parse()
    with pytest.raises(CalculatedAmountError):
        parser.parse()


def test_parser_dividend_calculated_amount_mismatch(create_parser):
    dividend = dict(DIVIDEND)
    dividend["Total Amount"] = "2.50"
    parser = create_parser([dividend])
    assert parser.can_parse()
    with pytest.raises(CalculatedAmountError):
        parser.parse()
