import csv
from decimal import Decimal
from datetime import datetime, timezone
from typing import Final

import pytest

from investir.config import config
from investir.exceptions import (
    OrderDateError,
    TransactionTypeError,
)
from investir.parsers.simple import SimpleParser
from investir.transaction import Acquisition, Disposal


TIMESTAMP = datetime(2021, 7, 26, 7, 41, 32, 582, tzinfo=timezone.utc)

ACQUISITION: Final = {
    "Action": "Acquisition",
    "Timestamp": TIMESTAMP,
    "Amount": "1330.20",
    "Ticker": "AMZN",
    "Quantity": "10.0",
    "Fees": "5.2",
}

DISPOSAL: Final = {
    "Action": "Disposal",
    "Timestamp": TIMESTAMP,
    "Amount": "1111.85",
    "Ticker": "SWKS",
    "Quantity": "2.1",
    "Fees": "6.4",
}


@pytest.fixture(name="create_parser")
def fixture_create_parser(tmp_path):
    config.include_fx_fees = True

    def _create_parser(rows):
        csv_file = tmp_path / "transactions.csv"
        with csv_file.open("w", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=SimpleParser.FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        return SimpleParser(csv_file)

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
    return SimpleParser(csv_file)


def test_parser_happy_path(create_parser):
    acquisition = dict(ACQUISITION)

    disposal = DISPOSAL

    dividend = {
        "Action": "Dividend",
        "Timestamp": TIMESTAMP,
        "Amount": "2.47",
        "Ticker": "SWKS",
    }

    deposit = {
        "Action": "Deposit",
        "Timestamp": TIMESTAMP,
        "Amount": "1000.00",
    }

    withdrawal = {
        "Action": "Withdrawal",
        "Timestamp": TIMESTAMP,
        "Amount": "500.25",
    }

    interest = {
        "Action": "Interest",
        "Timestamp": TIMESTAMP,
        "Amount": "4.65",
    }

    parser = create_parser(
        [
            acquisition,
            disposal,
            dividend,
            deposit,
            withdrawal,
            interest,
        ]
    )

    assert type(parser).name() == "Simple"
    assert parser.can_parse()

    parser_result = parser.parse()
    assert len(parser_result.orders) == 2

    order = parser_result.orders[0]
    assert isinstance(order, Acquisition)
    assert order.timestamp == TIMESTAMP
    assert order.amount == Decimal("1325.00")
    assert order.ticker == "AMZN"
    assert order.quantity == Decimal("10")
    assert order.fees == Decimal("5.2")

    order = parser_result.orders[1]
    assert isinstance(order, Disposal)
    assert order.timestamp == TIMESTAMP
    assert order.amount == Decimal("1118.25")
    assert order.ticker == "SWKS"
    assert order.quantity == Decimal("2.1")
    assert order.fees == Decimal("6.4")

    assert len(parser_result.dividends) == 1

    dividend = parser_result.dividends[0]
    assert dividend.timestamp == TIMESTAMP
    assert dividend.amount == Decimal("2.47")
    assert dividend.ticker == "SWKS"
    assert dividend.withheld is None

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


def test_parser_order_too_old(create_parser):
    order = dict(ACQUISITION)
    order["Timestamp"] = "2008-04-05T09:00:00.000Z"
    parser = create_parser([order])
    assert parser.can_parse()
    with pytest.raises(OrderDateError):
        parser.parse()
