import csv
from decimal import Decimal
from datetime import datetime, timedelta, timezone

import pytest

from investir.parser.exceptions import (
    ParserError,
    CalculatedAmountError,
    FeeError,
    OrderTooError,
)
from investir.parser.freetrade import FreetradeParser
from investir.transaction import Acquisition, Disposal


@pytest.fixture(name="create_parser")
def fixture_create_parser(tmp_path):
    def _create_parser(rows):
        csv_file = tmp_path / "transactions.csv"
        with csv_file.open("w", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=FreetradeParser.FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        return FreetradeParser(csv_file)

    return _create_parser


@pytest.fixture(name="create_parser_format_unrecognised")
def fixture_create_parser_format_unrecognised(tmp_path):
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
    timestamp = datetime(2021, 7, 26, 7, 41, 32, 582, tzinfo=timezone.utc)

    parser = create_parser(
        [
            {
                "Type": "ORDER",
                "Timestamp": timestamp + timedelta(hours=1),
                "Account Currency": "GBP",
                "Total Amount": Decimal("1330.20"),
                "Buy / Sell": "BUY",
                "Ticker": "AMZN",
                "Price per Share in Account Currency": Decimal("132.5"),
                "Stamp Duty": Decimal("5.2"),
                "Quantity": Decimal("10.0"),
                "FX Fee Amount": "",
            },
            {
                "Type": "ORDER",
                "Timestamp": timestamp,
                "Account Currency": "GBP",
                "Total Amount": Decimal("1111.85"),
                "Buy / Sell": "SELL",
                "Ticker": "SWKS",
                "Price per Share in Account Currency": Decimal("532.5"),
                "Stamp Duty": "",
                "Quantity": Decimal("2.1"),
                "FX Fee Amount": Decimal("6.4"),
            },
            {
                "Type": "DIVIDEND",
                "Timestamp": timestamp,
                "Account Currency": "GBP",
                "Total Amount": "2.47",
                "Ticker": "SWKS",
                "ISIN": "US83088M1027",
                "Base FX Rate": "0.75440000",
                "FX Fee Amount": "0.00",
                "Dividend Ex Date": "2021-11-22",
                "Dividend Pay Date": "2021-12-14",
                "Dividend Eligible Quantity": "6.88764135",
                "Dividend Amount Per Share": "0.56000000",
                "Dividend Gross Distribution Amount": "3.86",
                "Dividend Net Distribution Amount": "3.28",
                "Dividend Withheld Tax Percentage": "15",
                "Dividend Withheld Tax Amount": "0.58",
            },
            {
                "Type": "TOP_UP",
                "Timestamp": timestamp + timedelta(hours=1),
                "Account Currency": "GBP",
                "Total Amount": "1000.00",
            },
            {
                "Type": "WITHDRAW",
                "Timestamp": timestamp,
                "Account Currency": "GBP",
                "Total Amount": "500.25",
            },
            {
                "Type": "INTEREST_FROM_CASH",
                "Timestamp": timestamp,
                "Account Currency": "GBP",
                "Total Amount": "4.65",
            },
            {"Type": "MONTHLY_STATEMENT"},
        ]
    )

    assert type(parser).name() == "Freetrade"

    assert parser.can_parse()

    parser_result = parser.parse()

    assert len(parser_result.orders) == 2

    order = parser_result.orders[0]
    assert isinstance(order, Disposal)
    assert order.timestamp == timestamp
    assert order.amount == Decimal("1118.25")
    assert order.ticker == "SWKS"
    assert order.quantity == Decimal("2.1")
    assert order.fees == Decimal("6.4")

    order = parser_result.orders[1]
    assert isinstance(order, Acquisition)
    assert order.timestamp == timestamp + timedelta(hours=1)
    assert order.amount == Decimal("1325.00")
    assert order.ticker == "AMZN"
    assert order.quantity == Decimal("10")
    assert order.fees == Decimal("5.2")

    assert len(parser_result.dividends) == 1
    dividend = parser_result.dividends[0]

    assert dividend.timestamp == timestamp
    assert dividend.amount == Decimal("2.47")
    assert dividend.ticker == "SWKS"
    assert dividend.withheld == Decimal("0.4375520000")

    assert len(parser_result.transfers) == 2

    transfer = parser_result.transfers[0]
    assert transfer.timestamp == timestamp
    assert transfer.amount == Decimal("-500.25")

    transfer = parser_result.transfers[1]
    assert transfer.timestamp == timestamp + timedelta(hours=1)
    assert transfer.amount == Decimal("1000.00")

    assert len(parser_result.interest) == 1
    interest = parser_result.interest[0]
    assert interest.timestamp == timestamp
    assert interest.amount == Decimal("4.65")


def test_parser_cannot_parse(create_parser_format_unrecognised):
    parser = create_parser_format_unrecognised
    assert parser.can_parse() is False


def test_parser_invalid_type(create_parser):
    parser = create_parser([{"Type": "Not Valid"}])

    assert parser.can_parse()

    with pytest.raises(ParserError):
        parser.parse()


def test_parser_invalid_buy_sell(create_parser):
    parser = create_parser([{"Type": "ORDER", "Buy / Sell": "Not Valid"}])

    assert parser.can_parse()

    with pytest.raises(ParserError):
        parser.parse()


def test_parser_invalid_account_currency(create_parser):
    parser = create_parser(
        [{"Type": "ORDER", "Buy / Sell": "BUY", "Account Currency": "USD"}]
    )

    assert parser.can_parse()

    with pytest.raises(ParserError):
        parser.parse()


def test_parser_stamp_duty_and_fx_fee_non_zero(create_parser):
    parser = create_parser(
        [
            {
                "Type": "ORDER",
                "Timestamp": "2024-03-08T17:53:45.673Z",
                "Account Currency": "GBP",
                "Total Amount": Decimal("0.0"),
                "Buy / Sell": "BUY",
                "Ticker": "AMZN",
                "Price per Share in Account Currency": Decimal("132.5"),
                "Stamp Duty": Decimal("5.2"),
                "Quantity": Decimal("10.0"),
                "FX Fee Amount": Decimal("1.2"),
            },
        ]
    )

    assert parser.can_parse()

    with pytest.raises(FeeError):
        parser.parse()


def test_parser_calculated_amount_mismatch(create_parser):
    parser = create_parser(
        [
            {
                "Type": "ORDER",
                "Timestamp": "2024-03-08T17:53:45.673Z",
                "Account Currency": "GBP",
                "Total Amount": Decimal("0.0"),
                "Buy / Sell": "BUY",
                "Ticker": "AMZN",
                "Price per Share in Account Currency": Decimal("132.5"),
                "Stamp Duty": Decimal("5.2"),
                "Quantity": Decimal("10.0"),
                "FX Fee Amount": "",
            },
        ]
    )

    assert parser.can_parse()

    with pytest.raises(CalculatedAmountError):
        parser.parse()


def test_parser_order_too_old(create_parser):
    parser = create_parser(
        [
            {
                "Type": "ORDER",
                "Timestamp": "2008-04-05T09:00:00.000Z",
                "Account Currency": "GBP",
                "Total Amount": Decimal("1330.20"),
                "Buy / Sell": "BUY",
                "Ticker": "AMZN",
                "Price per Share in Account Currency": Decimal("132.5"),
                "Stamp Duty": Decimal("5.2"),
                "Quantity": Decimal("10.0"),
                "FX Fee Amount": "",
            },
        ]
    )

    assert parser.can_parse()

    with pytest.raises(OrderTooError):
        parser.parse()
