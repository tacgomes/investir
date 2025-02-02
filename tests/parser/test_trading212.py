import csv
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from decimal import Decimal
from typing import Final

import pytest
from moneyed import Money

from investir.config import config
from investir.exceptions import (
    CalculatedAmountError,
    FeesError,
    OrderDateError,
    ParseError,
    TransactionTypeError,
)
from investir.parser.trading212 import Trading212Parser
from investir.transaction import Acquisition, Disposal
from investir.typing import ISIN, Ticker
from investir.utils import sterling

TIMESTAMP: Final = datetime(2021, 7, 26, 7, 41, 32, 582, tzinfo=timezone.utc)


ACQUISITION: Final = {
    "Action": "Market buy",
    "Time": TIMESTAMP,
    "ISIN": "AMZN-ISIN",
    "Ticker": "AMZN",
    "Name": "Amazon",
    "No. of shares": "10.0",
    "Price / share": "132.5",
    "Currency (Price / share)": "GBP",
    "Exchange rate": "1.0",
    "Total": "1330.20",
    "Currency (Total)": "GBP",
    "Stamp duty (GBP)": "5.2",
}


DISPOSAL: Final = {
    "Action": "Market sell",
    "Time": TIMESTAMP,
    "ISIN": "SWKS-ISIN",
    "Ticker": "SWKS",
    "Name": "Skyworks",
    "No. of shares": "2.1",
    "Price / share": "532.5",
    "Currency (Price / share)": "GBP",
    "Exchange rate": "1.0",
    "Total": "1111.85",
    "Currency (Total)": "GBP",
    "Stamp duty (GBP)": "",
    "Currency conversion fee": "6.4",
    "Currency (Currency conversion fee)": "GBP",
}


DIVIDEND: Final = {
    "Action": "Dividend (Ordinary)",
    "Time": TIMESTAMP,
    "ISIN": "SWKS-ISIN",
    "Ticker": "SWKS",
    "Name": "Skyworks",
    "No. of shares": "2.1",
    "Price / share": "532.5",
    "Currency (Price / share)": "USD",
    "Exchange rate": "1.0",
    "Total": "2.47",
    "Currency (Total)": "GBP",
    "Currency (Withholding tax)": "USD",
}


@pytest.fixture(name="create_parser")
def fixture_create_parser(tmp_path) -> Callable:
    config.reset()
    config.include_fx_fees = True

    def _create_parser(rows: Sequence[Mapping[str, str]]) -> Trading212Parser:
        csv_file = tmp_path / "transactions.csv"
        with csv_file.open("w", encoding="utf-8") as file:
            field_names = (
                Trading212Parser.INITIAL_FIELDS
                + Trading212Parser.MANDATORY_FIELDS
                + Trading212Parser.OPTIONAL_FIELDS
            )
            writer = csv.DictWriter(file, fieldnames=field_names)
            writer.writeheader()
            writer.writerows(rows)
        return Trading212Parser(csv_file)

    return _create_parser


@pytest.fixture(name="create_parser_format_unrecognised")
def fixture_create_parser_format_unrecognised(tmp_path) -> Callable:
    def _create_parser(fields: Sequence[str]):
        csv_file = tmp_path / "transactions.csv"
        with csv_file.open("w", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=fields)
            writer.writeheader()
        return Trading212Parser(csv_file)

    return _create_parser


def test_parser_happy_path(create_parser):  # noqa: PLR0915
    acquisition1 = ACQUISITION

    acquisition2 = dict(ACQUISITION)
    acquisition2["Finra fee (GBP)"] = "5.2"
    del acquisition2["Stamp duty (GBP)"]

    dividend1 = DIVIDEND
    dividend2 = dict(DIVIDEND)
    dividend2["Action"] = "Dividend (Dividends paid by us corporations)"
    dividend3 = dict(DIVIDEND)
    dividend3["Action"] = "Dividend (Dividends paid by foreign corporations)"

    deposit = {
        "Action": "Deposit",
        "Time": TIMESTAMP,
        "Total": "1000.00",
        "Currency (Total)": "GBP",
    }

    withdrawal = {
        "Action": "Withdrawal",
        "Time": TIMESTAMP,
        "Total": "-500.25",
        "Currency (Total)": "GBP",
    }

    interest = {
        "Action": "Interest on cash",
        "Time": TIMESTAMP,
        "Total": "4.65",
        "Currency (Total)": "GBP",
    }

    parser = create_parser(
        [
            acquisition1,
            DISPOSAL,
            acquisition2,
            dividend1,
            dividend2,
            dividend3,
            deposit,
            withdrawal,
            interest,
        ]
    )

    assert parser.can_parse()

    parser_result = parser.parse()
    assert len(parser_result.orders) == 3

    order = parser_result.orders[0]
    assert isinstance(order, Acquisition)
    assert order.timestamp == TIMESTAMP
    assert order.isin == ISIN("AMZN-ISIN")
    assert order.ticker == Ticker("AMZN")
    assert order.name == "Amazon"
    assert order.total == sterling("1325.00")
    assert order.quantity == Decimal("10")
    assert order.fees == sterling("5.2")

    order = parser_result.orders[1]
    assert isinstance(order, Disposal)
    assert order.timestamp == TIMESTAMP
    assert order.isin == ISIN("SWKS-ISIN")
    assert order.ticker == Ticker("SWKS")
    assert order.name == "Skyworks"
    assert order.total == sterling("1118.25")
    assert order.quantity == Decimal("2.1")
    assert order.fees == sterling("6.4")

    order = parser_result.orders[2]
    assert isinstance(order, Acquisition)
    assert order.fees == sterling("5.2")

    assert len(parser_result.dividends) == 3

    dividend = parser_result.dividends[0]
    assert dividend.timestamp == TIMESTAMP
    assert dividend.isin == ISIN("SWKS-ISIN")
    assert dividend.ticker == Ticker("SWKS")
    assert dividend.name == "Skyworks"
    assert dividend.total == sterling("2.47")
    assert dividend.withheld == Money("0.0", "USD")
    assert dividend == parser_result.dividends[1]
    assert dividend == parser_result.dividends[2]

    assert len(parser_result.transfers) == 2

    transfer = parser_result.transfers[0]
    assert transfer.timestamp == TIMESTAMP
    assert transfer.total == sterling("1000.00")

    transfer = parser_result.transfers[1]
    assert transfer.timestamp == TIMESTAMP
    assert transfer.total == sterling("-500.25")

    assert len(parser_result.interest) == 1

    interest = parser_result.interest[0]
    assert interest.timestamp == TIMESTAMP
    assert interest.total == sterling("4.65")


def test_parser_when_fx_fees_are_not_allowable_cost(create_parser):
    config.include_fx_fees = False

    order1 = dict(ACQUISITION)
    order1["Currency conversion fee"] = "5.2"
    order1["Currency (Currency conversion fee)"] = "GBP"
    del order1["Stamp duty (GBP)"]

    order2 = dict(DISPOSAL)

    order3 = {
        "Action": "Market buy",
        "Time": TIMESTAMP,
        "ISIN": "MSFT-ISIN",
        "Ticker": "MSFT",
        "Name": "Microsoft",
        "No. of shares": "10.0",
        "Price / share": "132.5",
        "Currency (Price / share)": "GBP",
        "Exchange rate": "1.0",
        "Total": "1326.30",
        "Currency (Total)": "GBP",
        "Stamp duty (GBP)": "1.3",
    }

    parser = create_parser([order1, order2, order3])

    parser_result = parser.parse()
    assert len(parser_result.orders) == 3

    order = parser_result.orders[0]
    assert isinstance(order, Acquisition)
    assert order.timestamp == TIMESTAMP
    assert order.isin == ISIN("AMZN-ISIN")
    assert order.ticker == Ticker("AMZN")
    assert order.name == Ticker("Amazon")
    assert order.total == sterling("1325.00")
    assert order.quantity == Decimal("10")
    assert order.fees == sterling("0.0")

    order = parser_result.orders[1]
    assert isinstance(order, Disposal)
    assert order.timestamp == TIMESTAMP
    assert order.isin == ISIN("SWKS-ISIN")
    assert order.ticker == Ticker("SWKS")
    assert order.name == "Skyworks"
    assert order.total == sterling("1118.25")
    assert order.quantity == Decimal("2.1")
    assert order.fees == sterling("0.0")

    order = parser_result.orders[2]
    assert isinstance(order, Acquisition)
    assert order.timestamp == TIMESTAMP
    assert order.isin == ISIN("MSFT-ISIN")
    assert order.ticker == Ticker("MSFT")
    assert order.name == "Microsoft"
    assert order.total == sterling("1325.00")
    assert order.quantity == Decimal("10.0")
    assert order.fees == sterling("1.3")


def test_parser_different_buy_sell_actions(create_parser):
    acquisition1 = dict(ACQUISITION)  # Market buy

    acquisition2 = dict(ACQUISITION)
    acquisition2["Action"] = "Limit buy"

    acquisition3 = dict(ACQUISITION)
    acquisition3["Action"] = "Stop buy"

    disposal1 = dict(DISPOSAL)  # Market sell

    disposal2 = dict(DISPOSAL)
    disposal2["Action"] = "Limit sell"

    disposal3 = dict(DISPOSAL)
    disposal3["Action"] = "Stop sell"

    parser = create_parser(
        [acquisition1, acquisition2, acquisition3, disposal1, disposal2, disposal3]
    )

    parser_result = parser.parse()
    assert len(parser_result.orders) == 6

    orders = parser_result.orders
    assert orders[0] == orders[1] == orders[2]
    assert orders[3] == orders[4] == orders[5]


def test_parser_cannot_parse(create_parser_format_unrecognised):
    # Fields don't start with initial fields
    parser = create_parser_format_unrecognised(Trading212Parser.MANDATORY_FIELDS)
    assert parser.can_parse() is False

    # One mandatory field is missing
    parser = create_parser_format_unrecognised(
        [*Trading212Parser.INITIAL_FIELDS, *Trading212Parser.MANDATORY_FIELDS[1:]]
    )
    assert parser.can_parse() is False

    # An unsupported field was found
    parser = create_parser_format_unrecognised(
        [
            *Trading212Parser.INITIAL_FIELDS,
            *Trading212Parser.MANDATORY_FIELDS,
            "Unknown Field",
        ]
    )
    assert parser.can_parse() is False


def test_parser_invalid_transaction_type(create_parser):
    order = dict(ACQUISITION)
    order["Action"] = "NOT-VALID"
    parser = create_parser([order])
    assert parser.can_parse()
    with pytest.raises(TransactionTypeError):
        parser.parse()

    config.strict = False
    parser.parse()


def test_parser_order_too_old(create_parser):
    order = dict(ACQUISITION)
    order["Time"] = "2008-04-05T09:00:00.000Z"
    parser = create_parser([order])
    assert parser.can_parse()
    with pytest.raises(OrderDateError):
        parser.parse()


def test_parser_stamp_duty_and_fx_fee_non_zero(create_parser):
    order = dict(ACQUISITION)
    order["Currency conversion fee"] = "1.2"
    order["Currency (Currency conversion fee)"] = "GBP"
    parser = create_parser([order])
    assert parser.can_parse()
    with pytest.raises(FeesError):
        parser.parse()


def test_parser_conversion_fee_but_no_fee_currency(create_parser):
    order = dict(ACQUISITION)
    order["Currency conversion fee"] = "3.2"
    order["Currency (Currency conversion fee)"] = ""
    parser = create_parser([order])
    assert parser.can_parse()
    with pytest.raises(ParseError):
        parser.parse()


def test_parser_stamp_duty_and_finra_fee_non_zero(create_parser):
    order = dict(ACQUISITION)
    order["Finra fee (GBP)"] = "1.2"
    parser = create_parser([order])
    assert parser.can_parse()
    with pytest.raises(FeesError):
        parser.parse()


def test_parser_currency_conversion_fee_different_than_total_currency(create_parser):
    order = dict(ACQUISITION)
    order["Total"] = "1326.20"
    order["Currency conversion fee"] = "1.2"
    order["Currency (Currency conversion fee)"] = "USD"
    del order["Stamp duty (GBP)"]
    parser = create_parser([order])
    assert parser.can_parse()
    with pytest.raises(TypeError):
        parser.parse()


def test_parser_dividend_tax_withheld_in_different_currency(create_parser):
    dividend = dict(DIVIDEND)
    dividend["Currency (Withholding tax)"] = "EUR"
    parser = create_parser([dividend])
    assert parser.can_parse()
    with pytest.raises(ParseError):
        parser.parse()


def test_parser_calculated_amount_mismatch(create_parser):
    order = dict(ACQUISITION)
    order["Total"] = "7.5"
    parser = create_parser([order])
    assert parser.can_parse()
    with pytest.raises(CalculatedAmountError):
        parser.parse()


def test_parser_dividend_with_conversion_fee(create_parser):
    dividend = dict(DIVIDEND)
    dividend["Currency conversion fee"] = "1.2"
    parser = create_parser([dividend])
    assert parser.can_parse()
    with pytest.raises(ParseError):
        parser.parse()
