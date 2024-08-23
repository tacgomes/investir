import csv
from collections.abc import Callable, Mapping, Sequence
from decimal import Decimal
from datetime import datetime, timezone
from typing import Final

import pytest

from investir.config import config
from investir.exceptions import (
    CalculatedAmountError,
    CurrencyError,
    FeesError,
    OrderDateError,
    ParseError,
    TransactionTypeError,
)
from investir.parsers.trading212 import Trading212Parser
from investir.transaction import Acquisition, Disposal
from investir.typing import ISIN, Ticker


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
    "Currency (Price / share)": "EUR",
    "Exchange rate": "1.0",
    "Total": "2.47",
    "Currency (Total)": "GBP",
    "Currency (Withholding tax)": "EUR",
}


@pytest.fixture(name="create_parser")
def fixture_create_parser(tmp_path) -> Callable:
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
def fixture_create_parser_format_unrecognised(tmp_path) -> Trading212Parser:
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
    return Trading212Parser(csv_file)


# pylint: disable=too-many-locals, too-many-statements
def test_parser_happy_path(create_parser):
    acquisition1 = ACQUISITION
    acquisition2 = dict(ACQUISITION)
    acquisition2["Action"] = "Limit buy"

    disposal1 = DISPOSAL
    disposal2 = dict(DISPOSAL)
    disposal2["Action"] = "Limit sell"

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
        "Total": "500.25",
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
            acquisition2,
            disposal1,
            disposal2,
            dividend1,
            dividend2,
            dividend3,
            deposit,
            withdrawal,
            interest,
        ]
    )

    assert type(parser).name() == "Trading212"
    assert parser.can_parse()

    parser_result = parser.parse()
    assert len(parser_result.orders) == 4

    order = parser_result.orders[0]
    assert isinstance(order, Acquisition)
    assert order.timestamp == TIMESTAMP
    assert order.isin == ISIN("AMZN-ISIN")
    assert order.ticker == Ticker("AMZN")
    assert order.name == "Amazon"
    assert order.amount == Decimal("1325.00")
    assert order.quantity == Decimal("10")
    assert order.fees == Decimal("5.2")
    assert order == parser_result.orders[1]

    order = parser_result.orders[2]
    assert isinstance(order, Disposal)
    assert order.timestamp == TIMESTAMP
    assert order.isin == ISIN("SWKS-ISIN")
    assert order.ticker == Ticker("SWKS")
    assert order.name == "Skyworks"
    assert order.amount == Decimal("1118.25")
    assert order.quantity == Decimal("2.1")
    assert order.fees == Decimal("6.4")
    assert order == parser_result.orders[3]

    assert len(parser_result.dividends) == 3
    dividend = parser_result.dividends[0]

    assert dividend.timestamp == TIMESTAMP
    assert dividend.isin == ISIN("SWKS-ISIN")
    assert dividend.ticker == Ticker("SWKS")
    assert dividend.name == "Skyworks"
    assert dividend.amount == Decimal("2.47")
    assert dividend.withheld is None
    assert dividend == parser_result.dividends[1]
    assert dividend == parser_result.dividends[2]

    assert len(parser_result.transfers) == 2

    transfer = parser_result.transfers[0]
    assert transfer.timestamp == TIMESTAMP
    assert transfer.amount == Decimal("1000.00")

    transfer = parser_result.transfers[1]
    assert transfer.timestamp == TIMESTAMP
    assert transfer.amount == Decimal("-500.25")

    assert len(parser_result.interest) == 1
    interest = parser_result.interest[0]
    assert interest.timestamp == TIMESTAMP
    assert interest.amount == Decimal("4.65")


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
    assert order.amount == Decimal("1325.00")
    assert order.quantity == Decimal("10")
    assert order.fees == Decimal("0.0")

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
    assert order.isin == ISIN("MSFT-ISIN")
    assert order.ticker == Ticker("MSFT")
    assert order.name == "Microsoft"
    assert order.amount == Decimal("1325.00")
    assert order.quantity == Decimal("10.0")
    assert order.fees == Decimal("1.3")


def test_parser_cannot_parse(create_parser_format_unrecognised):
    parser = create_parser_format_unrecognised
    assert parser.can_parse() is False


def test_parser_invalid_transaction_type(create_parser):
    order = dict(ACQUISITION)
    order["Action"] = "NOT-VALID"
    parser = create_parser([order])
    assert parser.can_parse()
    with pytest.raises(TransactionTypeError):
        parser.parse()


def test_parser_invalid_account_currency(create_parser):
    order = dict(ACQUISITION)
    order["Currency (Total)"] = "USD"
    parser = create_parser([order])
    assert parser.can_parse()
    with pytest.raises(CurrencyError):
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


def test_parser_stamp_duty_and_finra_fee_non_zero(create_parser):
    order = dict(ACQUISITION)
    order["Finra fee (GBP)"] = "1.2"
    parser = create_parser([order])
    assert parser.can_parse()
    with pytest.raises(FeesError):
        parser.parse()


def test_parser_currency_conversion_fee_not_in_pound_sterling(create_parser):
    order = dict(ACQUISITION)
    order["Currency conversion fee"] = "1.2"
    order["Currency (Currency conversion fee)"] = "USD"
    del order["Stamp duty (GBP)"]
    parser = create_parser([order])
    assert parser.can_parse()
    with pytest.raises(CurrencyError):
        parser.parse()


def test_parser_calculated_amount_mismatch(create_parser):
    order = dict(ACQUISITION)
    order["Total"] = "7.5"
    parser = create_parser([order])
    assert parser.can_parse()
    with pytest.raises(CalculatedAmountError):
        parser.parse()


def test_parser_dividend_tax_withheld_in_different_currency(create_parser):
    dividend = dict(DIVIDEND)
    dividend["Currency (Withholding tax)"] = "USD"
    parser = create_parser([dividend])
    assert parser.can_parse()
    with pytest.raises(ParseError):
        parser.parse()


def test_parser_dividend_with_conversion_fee(create_parser):
    dividend = dict(DIVIDEND)
    dividend["Currency conversion fee"] = "1.2"
    parser = create_parser([dividend])
    assert parser.can_parse()
    with pytest.raises(ParseError):
        parser.parse()
