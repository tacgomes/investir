import csv
import pytest

from decimal import Decimal

import datetime

from investir.config import Config
from investir.parser.exceptions import (
    ParserError,
    CalculatedAmountError,
    FeeError)
from investir.parser.freetrade import FreetradeParser
from investir.transaction import TransactionType


@pytest.fixture
def create_parser(tmp_path):
    def _create_parser(rows):
        input_file = tmp_path / 'transactions.csv'
        with open(input_file, 'w') as file:
            writer = csv.DictWriter(file, fieldnames=FreetradeParser.FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        config = Config(strict=True)
        return FreetradeParser(input_file, config)
    return _create_parser


@pytest.fixture
def create_parser_format_unrecognised(tmp_path):
    input_file = tmp_path / 'transactions.csv'
    with open(input_file, 'w') as file:
        writer = csv.DictWriter(file, fieldnames=('Field1', 'Field2'))
        writer.writeheader()
        writer.writerow({
            'Field1': "A",
            'Field2': "B",
        })
    config = Config(strict=True)
    return FreetradeParser(input_file, config)


def test_parser_happy_path(create_parser):
    parser = create_parser([
        {
            'Type': 'ORDER',
            'Timestamp': '2024-03-08T17:53:45.673Z',
            'Account Currency': 'GBP',
            'Total Amount': Decimal('1330.20'),
            'Buy / Sell': 'BUY',
            'Ticker': 'AMZN',
            'Price per Share in Account Currency': Decimal('132.5'),
            'Stamp Duty': Decimal('5.2'),
            'Quantity': Decimal('10.0'),
            'FX Fee Amount': ''
        },
        {
            'Type': 'ORDER',
            'Timestamp': '2024-02-15T15:43:01.342Z',
            'Account Currency': 'GBP',
            'Total Amount': Decimal('1111.85'),
            'Buy / Sell': 'SELL',
            'Ticker': 'SWKS',
            'Price per Share in Account Currency': Decimal('532.5'),
            'Stamp Duty': '',
            'Quantity': Decimal('2.1'),
            'FX Fee Amount': Decimal('6.4')
        },
        {'Type': 'TOP_UP'},
        {'Type': 'WITHDRAW'},
        {'Type': 'DIVIDEND'},
        {'Type': 'MONTHLY_STATEMENT'},
        {'Type': 'INTEREST_FROM_CASH'}
    ])

    assert parser.name() == 'Freetrade'

    assert parser.can_parse()

    transactions = parser.parse()
    assert len(transactions) == 2

    t = transactions[0]
    assert t.timestamp == datetime.datetime(
        2024, 3, 8, 17, 53, 45, 673000, tzinfo=datetime.UTC)
    assert t.ticker == 'AMZN'
    assert t.type == TransactionType.ACQUISITION
    assert t.price == Decimal('132.5')
    assert t.quantity == Decimal('10')
    assert t.fees == Decimal('5.2')

    t = transactions[1]
    assert t.timestamp == datetime.datetime(
        2024, 2, 15, 15, 43, 1, 342000, tzinfo=datetime.UTC)
    assert t.ticker == 'SWKS'
    assert t.type == TransactionType.DISPOSAL
    assert t.price == Decimal('532.5')
    assert t.quantity == Decimal('2.1')
    assert t.fees == Decimal('6.4')


def test_parser_cannot_parse(create_parser_format_unrecognised):
    parser = create_parser_format_unrecognised
    assert parser.can_parse() is False


def test_parser_invalid_type(create_parser):
    parser = create_parser([
        {'Type': 'Not Valid'}
    ])

    assert parser.can_parse()

    with pytest.raises(ParserError):
        parser.parse()


def test_parser_invalid_buy_sell(create_parser):
    parser = create_parser([
        {
            'Type': 'ORDER',
            'Buy / Sell': 'Not Valid'
        }
    ])

    assert parser.can_parse()

    with pytest.raises(ParserError):
        parser.parse()


def test_parser_invalid_account_currency(create_parser):
    parser = create_parser([
        {
            'Type': 'ORDER',
            'Buy / Sell': 'BUY',
            'Account Currency': 'USD'
        }
    ])

    assert parser.can_parse()

    with pytest.raises(ParserError):
        parser.parse()


def test_parser_stamp_duty_and_fx_fee_non_zero(create_parser):
    parser = create_parser([
        {
            'Type': 'ORDER',
            'Timestamp': '2024-03-08T17:53:45.673Z',
            'Account Currency': 'GBP',
            'Total Amount': Decimal('0.0'),
            'Buy / Sell': 'BUY',
            'Ticker': 'AMZN',
            'Price per Share in Account Currency': Decimal('132.5'),
            'Stamp Duty': Decimal('5.2'),
            'Quantity': Decimal('10.0'),
            'FX Fee Amount': Decimal('1.2')
        },
    ])

    assert parser.can_parse()

    with pytest.raises(FeeError):
        parser.parse()


def test_parser_calculated_amount_mismatch(create_parser):
    parser = create_parser([
        {
            'Type': 'ORDER',
            'Timestamp': '2024-03-08T17:53:45.673Z',
            'Account Currency': 'GBP',
            'Total Amount': Decimal('0.0'),
            'Buy / Sell': 'BUY',
            'Ticker': 'AMZN',
            'Price per Share in Account Currency': Decimal('132.5'),
            'Stamp Duty': Decimal('5.2'),
            'Quantity': Decimal('10.0'),
            'FX Fee Amount': ''
        },
    ])

    assert parser.can_parse()

    with pytest.raises(CalculatedAmountError):
        parser.parse()
