import csv
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from decimal import Decimal
from typing import Final

import pytest

from investir.config import config
from investir.exceptions import (
    CalculatedAmountError,
    FeesError,
    FieldUnknownError,
    InvestirError,
    OrderDateError,
    TransactionUnknownError,
)
from investir.parser.freetrade import FreetradeParser
from investir.transaction import Acquisition, Disposal, FreeShare
from investir.typing import ISIN, Ticker
from investir.utils import sterling

TIMESTAMP: Final = datetime(2021, 7, 26, 7, 41, 32, 582, tzinfo=timezone.utc)

LEGACY_FIELDS: Final = {
    "Total Amount",
    "Total Shares Amount",
}

RECENT_FIELDS: Final = {
    "Total Amount in Account Currency",
    "Total Amount in Instrument Currency",
    "Stock Split Ex Date",
    "Stock Split Pay Date",
    "Stock Split New ISIN",
    "Stock Split Rate of Share Outturn From",
    "Stock Split Rate of Share Outturn To",
    "Stock Split Maintain Holding of Initial ISIN",
    "Stock Split New Share Quantity",
    "Stock Split Rate of Cash Outturn Amount",
    "Stock Split Rate of Cash Outturn Currency",
    "Stock Split Cash Outturn Received Amount",
    "Stock Split Has Fractional Payout",
    "Stock Split Rate of Fractional Payout Amount",
    "Stock Split Rate of Fractional Payout Currency",
    "Stock Split Fractional Payout Cash Received Amount",
    "Stock Split Fractional Payout Cash Received Currency",
}

ACQUISITION: Final = {
    "Title": "Amazon",
    "Type": "ORDER",
    "Timestamp": TIMESTAMP,
    "Account Currency": "GBP",
    "Total Amount in Account Currency": "1330.20",
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
    "Total Amount in Account Currency": "1111.85",
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
    "Total Amount in Account Currency": "2.47",
    "Ticker": "SWKS",
    "ISIN": "SWKS-ISIN",
    "Base FX Rate": "0.75440000",
    "Dividend Eligible Quantity": "6.88764135",
    "Dividend Amount Per Share": "0.56000000",
    "Dividend Withheld Tax Percentage": "15",
    "Dividend Withheld Tax Amount": "0.58",
}


@pytest.fixture
def make_parser(tmp_path) -> Callable:
    def _wrapper(
        rows: Sequence[Mapping[str, str]], legacy_fields: bool = False
    ) -> FreetradeParser:
        csv_file = tmp_path / "transactions.csv"
        with csv_file.open("w", encoding="utf-8") as file:
            if not legacy_fields:
                field_names = set(FreetradeParser.FIELDS) - LEGACY_FIELDS
            else:
                field_names = set(FreetradeParser.FIELDS) - RECENT_FIELDS
            writer = csv.DictWriter(file, fieldnames=field_names)
            writer.writeheader()
            writer.writerows(rows)
        return FreetradeParser(csv_file)

    return _wrapper


@pytest.fixture
def make_parser_with_custom_fields(tmp_path) -> Callable:
    def _wrapper(fields: Sequence[str]):
        csv_file = tmp_path / "transactions.csv"
        with csv_file.open("w", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=fields)
            writer.writeheader()
        return FreetradeParser(csv_file)

    return _wrapper


def test_parser_happy_path(make_parser):
    acquisition = ACQUISITION
    disposal = DISPOSAL
    dividend = DIVIDEND

    deposit = {
        "Type": "TOP_UP",
        "Timestamp": TIMESTAMP,
        "Account Currency": "GBP",
        "Total Amount in Account Currency": "1000.00",
    }

    withdrawal = {
        "Type": "WITHDRAWAL",
        "Timestamp": TIMESTAMP,
        "Account Currency": "GBP",
        "Total Amount in Account Currency": "500.25",
    }

    interest = {
        "Type": "INTEREST_FROM_CASH",
        "Timestamp": TIMESTAMP,
        "Account Currency": "GBP",
        "Total Amount in Account Currency": "4.65",
    }

    monthly_statement = {"Type": "MONTHLY_STATEMENT"}
    tax_certificate = {"Type": "TAX_CERTIFICATE"}

    parser = make_parser(
        [
            acquisition,
            disposal,
            dividend,
            deposit,
            withdrawal,
            interest,
            monthly_statement,
            tax_certificate,
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
    assert order.total == sterling("1111.85")
    assert order.quantity == Decimal("2.1")
    assert order.fees.total == sterling("6.4")

    order = parser_result.orders[1]
    assert isinstance(order, Acquisition)
    assert order.timestamp == TIMESTAMP
    assert order.isin == ISIN("AMZN-ISIN")
    assert order.ticker == Ticker("AMZN")
    assert order.name == "Amazon"
    assert order.total == sterling("1330.20")
    assert order.quantity == Decimal("10")
    assert order.fees.total == sterling("5.2")

    assert len(parser_result.dividends) == 1
    dividend = parser_result.dividends[0]

    assert dividend.timestamp == TIMESTAMP
    assert dividend.isin == ISIN("SWKS-ISIN")
    assert dividend.name == "Skyworks"
    assert dividend.ticker == Ticker("SWKS")
    assert dividend.total == sterling("2.47")
    assert dividend.withheld == sterling("0.4375520000")

    assert len(parser_result.transfers) == 2

    transfer = parser_result.transfers[0]
    assert transfer.timestamp == TIMESTAMP
    assert transfer.total == sterling("-500.25")

    transfer = parser_result.transfers[1]
    assert transfer.timestamp == TIMESTAMP
    assert transfer.total == sterling("1000.00")

    assert len(parser_result.interest) == 1
    interest = parser_result.interest[0]
    assert interest.timestamp == TIMESTAMP
    assert interest.total == sterling("4.65")


def test_parser_legacy_fields(make_parser):
    acquisition = {
        "Title": "Amazon",
        "Type": "ORDER",
        "Timestamp": TIMESTAMP,
        "Account Currency": "GBP",
        "Total Amount": "1330.20",
        "Total Shares Amount": "0.0",
        "Buy / Sell": "BUY",
        "Ticker": "AMZN",
        "ISIN": "AMZN-ISIN",
        "Price per Share in Account Currency": "132.5",
        "Stamp Duty": "5.2",
        "Quantity": "10.0",
    }

    parser = make_parser([acquisition], legacy_fields=True)
    assert parser.can_parse()
    assert len(parser.parse().orders) == 1


def test_parser_with_missing_required_field(make_parser_with_custom_fields):
    fields = list(FreetradeParser.FIELDS)
    fields.remove("Total Amount in Account Currency")
    fields.remove("Total Amount")
    parser = make_parser_with_custom_fields(fields)
    assert parser.can_parse() is False

    for field in ["Type", "Timestamp", "Account Currency"]:
        fields = list(FreetradeParser.FIELDS)
        fields.remove(field)
        parser = make_parser_with_custom_fields(fields)
        assert parser.can_parse() is False, f"{field} field test failed"


def test_parser_with_unknown_field(make_parser_with_custom_fields):
    parser = make_parser_with_custom_fields([*FreetradeParser.FIELDS, "Unknown field"])
    assert parser.can_parse() is True

    with pytest.raises(FieldUnknownError):
        parser.parse()

    config.strict = False
    parser.parse()


def test_parser_invalid_transaction_type(make_parser):
    order = dict(ACQUISITION)
    order["Type"] = "NOT-VALID"
    parser = make_parser([order])
    assert parser.can_parse()
    with pytest.raises(TransactionUnknownError):
        parser.parse()

    config.strict = False
    parser.parse()


def test_parser_invalid_buy_sell(make_parser):
    order = dict(ACQUISITION)
    order["Buy / Sell"] = "NOT-VALID"
    parser = make_parser([order])
    assert parser.can_parse()
    with pytest.raises(TransactionUnknownError):
        parser.parse()


def test_parser_stamp_duty_and_fx_fee_non_zero(make_parser):
    order = dict(ACQUISITION)
    order["FX Fee Amount"] = "1.2"
    parser = make_parser([order])
    assert parser.can_parse()
    with pytest.raises(FeesError):
        parser.parse()


def test_parser_order_too_old(make_parser):
    order = dict(ACQUISITION)
    order["Timestamp"] = "2008-04-05T09:00:00.000Z"
    parser = make_parser([order])
    assert parser.can_parse()
    with pytest.raises(OrderDateError):
        parser.parse()


def test_parser_order_calculated_amount_mismatch(make_parser):
    order = dict(ACQUISITION)
    order["Total Amount in Account Currency"] = "7.5"
    parser = make_parser([order])
    assert parser.can_parse()
    with pytest.raises(CalculatedAmountError):
        parser.parse()


def test_parser_dividend_calculated_amount_mismatch(make_parser):
    dividend = dict(DIVIDEND)
    dividend["Total Amount in Account Currency"] = "2.50"
    parser = make_parser([dividend])
    assert parser.can_parse()
    with pytest.raises(CalculatedAmountError):
        parser.parse()


def test_parser_free_share(make_parser):
    free_share = {
        "Title": "ChipMOS TECH ADR",
        "Type": "FREESHARE_ORDER",
        "Timestamp": TIMESTAMP,
        "Account Currency": "GBP",
        "Total Amount in Account Currency": "11.88",
        "Ticker": "IMOS",
        "ISIN": "US16965P2020",
        "Quantity": "1.00",
        "Order ID": "MQ7MF265KZEE",
    }

    parser = make_parser([free_share])
    assert parser.can_parse()

    parser_result = parser.parse()
    assert len(parser_result.orders) == 1

    order = parser_result.orders[0]
    assert isinstance(order, FreeShare)
    assert order.timestamp == TIMESTAMP
    assert order.isin == ISIN("US16965P2020")
    assert order.ticker == Ticker("IMOS")
    assert order.name == "ChipMOS TECH ADR"
    assert order.total == sterling("11.88")
    assert order.quantity == Decimal("1.00")
    assert order.tr_id == "MQ7MF265KZEE"


def test_parser_internal_transfer_inbound(make_parser):
    """Test internal transfer into account (e.g., from GIA to ISA)."""
    internal_transfer = {
        "Title": "Internal Transfer from GIA",
        "Type": "INTERNAL_TRANSFER",
        "Timestamp": TIMESTAMP,
        "Account Currency": "GBP",
        "Total Amount in Account Currency": "10000.00",
    }

    parser = make_parser([internal_transfer])
    assert parser.can_parse()

    parser_result = parser.parse()
    assert len(parser_result.transfers) == 1

    transfer = parser_result.transfers[0]
    assert transfer.timestamp == TIMESTAMP
    assert transfer.total == sterling("10000.00")


def test_parser_internal_transfer_outbound(make_parser):
    """Test internal transfer out of account (e.g., to ISA)."""
    internal_transfer = {
        "Title": "Internal Transfer to ISA",
        "Type": "INTERNAL_TRANSFER",
        "Timestamp": TIMESTAMP,
        "Account Currency": "GBP",
        "Total Amount in Account Currency": "5000.00",
    }

    parser = make_parser([internal_transfer])
    assert parser.can_parse()

    parser_result = parser.parse()
    assert len(parser_result.transfers) == 1

    transfer = parser_result.transfers[0]
    assert transfer.timestamp == TIMESTAMP
    assert transfer.total == sterling("-5000.00")


def test_parser_internal_transfer_unknown_type(make_parser):
    """Test internal transfer with unknown title format."""
    internal_transfer = {
        "Title": "Internal Transfer Unknown",
        "Type": "INTERNAL_TRANSFER",
        "Timestamp": TIMESTAMP,
        "Account Currency": "GBP",
        "Total Amount in Account Currency": "1000.00",
    }

    parser = make_parser([internal_transfer])
    assert parser.can_parse()

    with pytest.raises(InvestirError):
        parser.parse()

    config.strict = False
    parser.parse()
