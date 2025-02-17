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

LEGACY_FIELDS: Final = {
    "Total (GBP)",
    "Currency conversion fee (GBP)",
    "Transaction fee (GBP)",
    "Finra fee (GBP)",
}


RECENT_FIELDS: Final = {
    "Total",
    "Currency (Total)",
    "Currency conversion fee",
    "Currency (Currency conversion fee)",
    "Finra fee",
    "Currency (Finra fee)",
    "Transaction fee",
    "Currency (Transaction fee)",
}


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

CASH_INTEREST: Final = {
    "Action": "Interest on cash",
    "Time": TIMESTAMP,
    "Total": "4.65",
    "Currency (Total)": "GBP",
}


@pytest.fixture(name="create_parser")
def fixture_create_parser(tmp_path) -> Callable:
    config.reset()

    def _create_parser(
        rows: Sequence[Mapping[str, str]], legacy_fields: bool = False
    ) -> Trading212Parser:
        csv_file = tmp_path / "transactions.csv"
        with csv_file.open("w", encoding="utf-8") as file:
            if not legacy_fields:
                field_names = set(Trading212Parser.FIELDS) - LEGACY_FIELDS
            else:
                field_names = set(Trading212Parser.FIELDS) - RECENT_FIELDS
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


def test_parser_happy_path(create_parser):
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

    result_adjustment = {"Action": "Result adjustment"}
    card_debit = {"Action": "Card debit"}
    spending_cashback = {"Action": "Spending cashback"}
    currency_conversion = {"Action": "Currency conversion"}

    parser = create_parser(
        [
            ACQUISITION,
            DISPOSAL,
            DIVIDEND,
            deposit,
            withdrawal,
            CASH_INTEREST,
            result_adjustment,
            card_debit,
            spending_cashback,
            currency_conversion,
        ]
    )

    assert parser.can_parse()

    parser_result = parser.parse()
    assert len(parser_result.orders) == 2

    order = parser_result.orders[0]
    assert isinstance(order, Acquisition)
    assert order.timestamp == TIMESTAMP
    assert order.isin == ISIN("AMZN-ISIN")
    assert order.ticker == Ticker("AMZN")
    assert order.name == "Amazon"
    assert order.total == sterling("1330.20")
    assert order.quantity == Decimal("10")
    assert order.fees.total == sterling("5.2")

    order = parser_result.orders[1]
    assert isinstance(order, Disposal)
    assert order.timestamp == TIMESTAMP
    assert order.isin == ISIN("SWKS-ISIN")
    assert order.ticker == Ticker("SWKS")
    assert order.name == "Skyworks"
    assert order.total == sterling("1111.85")
    assert order.quantity == Decimal("2.1")
    assert order.fees.total == sterling("6.4")

    assert len(parser_result.dividends) == 1

    dividend = parser_result.dividends[0]
    assert dividend.timestamp == TIMESTAMP
    assert dividend.isin == ISIN("SWKS-ISIN")
    assert dividend.ticker == Ticker("SWKS")
    assert dividend.name == "Skyworks"
    assert dividend.total == sterling("2.47")
    assert dividend.withheld == Money("0.0", "USD")

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


def test_parser_different_dividends_actions(create_parser):
    dividend1 = dict(DIVIDEND)  # Dividend (Ordinary)

    dividend2 = dict(DIVIDEND)
    dividend2["Action"] = "Dividend (Dividend)"

    dividend3 = dict(DIVIDEND)
    dividend3["Action"] = "Dividend (Dividends paid by us corporations)"

    dividend4 = dict(DIVIDEND)
    dividend4["Action"] = "Dividend (Dividends paid by foreign corporations)"

    parser = create_parser([dividend1, dividend2, dividend3, dividend4])

    parser_result = parser.parse()
    assert len(parser_result.dividends) == 4

    dividends = parser_result.dividends
    assert dividends[0] == dividends[1] == dividends[2] == dividends[3]


def test_parser_different_interest_actions(create_parser):
    interest1 = dict(CASH_INTEREST)

    interest2 = dict(CASH_INTEREST)
    interest2["Action"] = "Lending interest"

    parser = create_parser([interest1, interest2])

    parser_result = parser.parse()
    assert len(parser_result.interest) == 2

    interest = parser_result.interest
    assert interest[0] == interest[1]


def test_parser_different_fee_types(create_parser):
    order1 = dict(ACQUISITION)
    del order1["Stamp duty (GBP)"]
    order1["Total"] = "1333.40"
    order1["Stamp duty reserve tax (GBP)"] = "5.2"
    order1["Currency conversion fee"] = "3.2"
    order1["Currency (Currency conversion fee)"] = "GBP"

    order2 = dict(ACQUISITION)
    del order2["Stamp duty (GBP)"]
    order2["Total"] = "1334.30"
    order2["Currency (Total)"] = "GBP"
    order2["Currency conversion fee"] = "3.2"
    order2["Currency (Currency conversion fee)"] = "GBP"
    order2["Transaction fee"] = "2.1"
    order2["Currency (Transaction fee)"] = "GBP"
    order2["Finra fee"] = "4.0"
    order2["Currency (Finra fee)"] = "GBP"

    parser = create_parser([order1, order2])

    parser_result = parser.parse()
    assert len(parser_result.orders) == 2

    order = parser_result.orders[0]
    assert order.total == sterling("1333.40")
    assert order.fees.total == sterling("8.4")

    order = parser_result.orders[1]
    assert order.total == sterling("1334.30")
    assert order.fees.total == sterling("9.3")


def test_parser_legacy_fields(create_parser):
    acquisition = {
        "Action": "Market buy",
        "Time": TIMESTAMP,
        "ISIN": "AMZN-ISIN",
        "Ticker": "AMZN",
        "Name": "Amazon",
        "No. of shares": "10.0",
        "Price / share": "132.5",
        "Currency (Price / share)": "GBP",
        "Exchange rate": "1.0",
        "Total (GBP)": "1334.30",
        "Currency conversion fee (GBP)": "3.2",
        "Transaction fee (GBP)": "2.1",
        "Finra fee (GBP)": "4.0",
    }

    parser = create_parser([acquisition], legacy_fields=True)
    assert parser.can_parse()

    parser_result = parser.parse()
    assert len(parser_result.orders) == 1

    order = parser_result.orders[0]
    assert order.total == sterling("1334.30")
    assert order.fees.total == sterling("9.3")


def test_parser_cannot_parse(create_parser_format_unrecognised):
    # An unsupported field was found
    parser = create_parser_format_unrecognised(
        [*Trading212Parser.FIELDS, "Unknown Field"]
    )
    assert parser.can_parse() is False

    # Total field is missing
    fields = list(Trading212Parser.FIELDS)
    fields.remove("Total")
    fields.remove("Total (GBP)")
    parser = create_parser_format_unrecognised(fields)
    assert parser.can_parse() is False

    # Action or Time fields are missing
    for field in ["Action", "Time"]:
        fields = list(Trading212Parser.FIELDS)
        fields.remove(field)
        parser = create_parser_format_unrecognised(fields)
        assert parser.can_parse() is False, f"{field} field test failed"


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


def test_parser_stamp_duty_and_stamp_duty_reserve_tax_non_zero(create_parser):
    order = dict(ACQUISITION)
    order["Stamp duty reserve tax (GBP)"] = "5.2"
    parser = create_parser([order])
    assert parser.can_parse()
    with pytest.raises(FeesError):
        parser.parse()


def test_parser_stamp_duty_and_finra_fee_non_zero(create_parser):
    order = dict(ACQUISITION)
    order["Finra fee"] = "1.2"
    order["Currency (Finra fee)"] = "GBP"
    parser = create_parser([order])
    assert parser.can_parse()
    with pytest.raises(FeesError):
        parser.parse()


def test_parser_stamp_duty_and_sec_fee_non_zero(create_parser):
    order = dict(ACQUISITION)
    order["Transaction fee"] = "1.2"
    order["Currency (Transaction fee)"] = "USD"
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
