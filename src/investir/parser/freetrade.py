import csv
import logging

from decimal import Decimal
from pathlib import Path

from dateutil.parser import parse as parse_timestamp

from .exceptions import (
    ParserError,
    CalculatedAmountError,
    FeeError)
from .factory import ParserFactory
from .parser import Parser
from .utils import read_decimal
from ..config import Config
from ..transaction import Transaction, TransactionType

logger = logging.getLogger(__name__)


class FreetradeParser(Parser):
    FIELDS = (
        'Title',
        'Type',
        'Timestamp',
        'Account Currency',
        'Total Amount',
        'Buy / Sell',
        'Ticker',
        'ISIN',
        'Price per Share in Account Currency',
        'Stamp Duty',
        'Quantity',
        'Venue',
        'Order ID',
        'Order Type',
        'Instrument Currency',
        'Total Shares Amount',
        'Price per Share',
        'FX Rate',
        'Base FX Rate',
        'FX Fee (BPS)',
        'FX Fee Amount',
        'Dividend Ex Date',
        'Dividend Pay Date',
        'Dividend Eligible Quantity',
        'Dividend Amount Per Share',
        'Dividend Gross Distribution Amount',
        'Dividend Net Distribution Amount',
        'Dividend Withheld Tax Percentage',
        'Dividend Withheld Tax Amount'
    )

    def __init__(self, input_file: Path, config: Config) -> None:
        self.input_file = input_file
        self.config = config

    def name(self) -> str:
        return 'Freetrade'

    def can_parse(self) -> bool:
        with open(self.input_file, encoding='utf-8') as f:
            reader = csv.DictReader(f)
            if reader.fieldnames:
                return tuple(reader.fieldnames) == self.FIELDS

        return False

    def parse(self) -> list[Transaction]:
        transactions = []
        with open(self.input_file, encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                transact = self._parse_row(row)
                if transact is not None:
                    logger.debug('Parsed %s as %s\n', row, transact)
                    transactions.append(transact)

        return transactions

    def _parse_row(self, row: dict[str, str]) -> Transaction | None:
        if row['Type'] == 'ORDER':
            return self._parse_row_order_type(row)

        if row['Type'] not in (
            'TOP_UP',
            'WITHDRAW',
            'DIVIDEND',
            'INTEREST_FROM_CASH',
            'MONTHLY_STATEMENT'
        ):
            raise ParserError(
                self.input_file.name,
                f'Unrecognised value for `Type` field: {row["Type"]}')

        return None

    def _parse_row_order_type(self, row: dict[str, str]) -> Transaction:
        action = row['Buy / Sell']

        if action == 'BUY':
            transact_type = TransactionType.ACQUISITION
        elif action == 'SELL':
            transact_type = TransactionType.DISPOSAL
        else:
            raise ParserError(
                self.input_file.name,
                f'Unrecognised value for `Buy / Sell` field: {action}')

        if row['Account Currency'] != 'GBP':
            raise ParserError(
                self.input_file.name,
                '`Account currency` field must be set to GBP')

        timestamp = parse_timestamp(row['Timestamp'])
        total_amount = Decimal(row['Total Amount'])
        ticker = row['Ticker']
        price = Decimal(row['Price per Share in Account Currency'])
        quantity = Decimal(row['Quantity'])
        stamp_duty = read_decimal(row['Stamp Duty'])
        fx_fee_amount = read_decimal(row['FX Fee Amount'])

        if stamp_duty and fx_fee_amount:
            raise FeeError(self.input_file.name)

        fees = stamp_duty + fx_fee_amount

        calculated_ta = price * quantity
        if transact_type == TransactionType.ACQUISITION:
            calculated_ta += fees
        else:
            calculated_ta -= fees
        calculated_ta = round(calculated_ta, 2)

        if total_amount != calculated_ta:
            raise CalculatedAmountError(
                self.input_file.name, calculated_ta, total_amount)

        return Transaction(
            timestamp,
            ticker,
            transact_type,
            price,
            quantity,
            fees)


ParserFactory.register_parser(FreetradeParser)
