import csv
import logging

from decimal import Decimal, ROUND_DOWN
from pathlib import Path

from dateutil.parser import parse as parse_timestamp

from .exceptions import (
    ParserError,
    CalculatedAmountError,
    FeeError)
from .parser import Parser, ParsingResult
from .utils import read_decimal
from ..config import Config
from ..transaction import (
    Order, OrderType,
    Dividend,
    Transfer, TransferType,
    Interest)

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

    def __init__(self, csv_file: Path, config: Config) -> None:
        self._csv_file = csv_file
        self._config = config
        self._orders: list[Order] = []
        self._dividends: list[Dividend] = []
        self._transfers: list[Transfer] = []
        self._interest: list[Interest] = []

    @staticmethod
    def name() -> str:
        return 'Freetrade'

    def can_parse(self) -> bool:
        with self._csv_file.open(encoding='utf-8') as file:
            reader = csv.DictReader(file)
            if reader.fieldnames:
                return tuple(reader.fieldnames) == self.FIELDS

        return False

    def parse(self) -> ParsingResult:
        parse_fn = {
            'ORDER': self._parse_order,
            'DIVIDEND': self._parse_dividend,
            'TOP_UP': self._parse_transfer,
            'WITHDRAW': self._parse_transfer,
            'INTEREST_FROM_CASH': self._parse_interest,
            'MONTHLY_STATEMENT': lambda _: None
        }

        with self._csv_file.open(encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                tr_type = row['Type']
                if fn := parse_fn.get(tr_type):
                    fn(row)
                else:
                    raise ParserError(
                        self._csv_file.name,
                        f'Unrecognised value for `Type` field: {tr_type}')

        return ParsingResult(
            self._orders, self._dividends, self._transfers, self._interest)

    def _parse_order(self, row: dict[str, str]) -> None:
        action = row['Buy / Sell']

        if action == 'BUY':
            transact_type = OrderType.ACQUISITION
        elif action == 'SELL':
            transact_type = OrderType.DISPOSAL
        else:
            raise ParserError(
                self._csv_file.name,
                f'Unrecognised value for `Buy / Sell` field: {action}')

        if row['Account Currency'] != 'GBP':
            raise ParserError(
                self._csv_file.name,
                '`Account currency` field must be set to GBP')

        timestamp = parse_timestamp(row['Timestamp'])
        total_amount = Decimal(row['Total Amount'])
        ticker = row['Ticker']
        price = Decimal(row['Price per Share in Account Currency'])
        quantity = Decimal(row['Quantity'])
        order_id = row['Order ID']
        stamp_duty = read_decimal(row['Stamp Duty'])
        fx_fee_amount = read_decimal(row['FX Fee Amount'])

        if stamp_duty and fx_fee_amount:
            raise FeeError(self._csv_file.name)

        fees = stamp_duty + fx_fee_amount

        calculated_ta = price * quantity
        if transact_type == OrderType.ACQUISITION:
            calculated_ta += fees
        else:
            calculated_ta -= fees
        calculated_ta = round(calculated_ta, 2)

        if total_amount != calculated_ta:
            raise CalculatedAmountError(
                self._csv_file.name, calculated_ta, total_amount)

        self._orders.append(Order(
            timestamp,
            ticker,
            transact_type,
            price,
            quantity,
            fees,
            order_id))

        logging.debug('Parsed row %s as %s\n', row, self._orders[-1])

    def _parse_dividend(self, row: dict[str, str]):
        timestamp = parse_timestamp(row['Timestamp'])
        total_amount = Decimal(row['Total Amount'])
        ticker = row['Ticker']
        base_fx_rate = read_decimal(row['Base FX Rate'], Decimal('1.0'))
        eligible_quantity = Decimal(row['Dividend Eligible Quantity'])
        amount_per_share = Decimal(row['Dividend Amount Per Share'])
        withheld_tax_percentage = Decimal(
            row['Dividend Withheld Tax Percentage'])
        withheld_tax_amount = Decimal(row['Dividend Withheld Tax Amount'])

        calculated_ta = (
            amount_per_share
            * eligible_quantity
            * ((Decimal(100) - withheld_tax_percentage) / 100)
            * base_fx_rate)

        rounded_calculated_ta = calculated_ta.quantize(
            Decimal('1.00'), rounding=ROUND_DOWN)

        if total_amount != rounded_calculated_ta:
            # Warning instead of exception because on Freetrade
            # the total amount is occasionally off by one cent.
            logger.warning(
                'Calculated amount (£%s ~= £%s) differs from the amount read '
                '(£%s) for row %s\n',
                calculated_ta, rounded_calculated_ta, total_amount, row)

        self._dividends.append(Dividend(
            timestamp,
            ticker,
            total_amount,
            withheld_tax_amount * base_fx_rate))

        logging.debug('Parsed row %s as %s\n', row, self._dividends[-1])

    def _parse_transfer(self, row: dict[str, str]):
        timestamp = parse_timestamp(row['Timestamp'])
        tr_type = row['Type']
        total_amount = Decimal(row['Total Amount'])

        if tr_type == 'TOP_UP':
            transfer_type = TransferType.DEPOSIT
        elif tr_type == 'WITHDRAW':
            transfer_type = TransferType.WITHDRAW
        else:
            assert False

        self._transfers.append(Transfer(
            timestamp,
            transfer_type,
            total_amount))

        logging.debug('Parsed row %s as %s\n', row, self._transfers[-1])

    def _parse_interest(self, row: dict[str, str]):
        timestamp = parse_timestamp(row['Timestamp'])
        total_amount = Decimal(row['Total Amount'])

        self._interest.append(Interest(
            timestamp,
            total_amount))

        logging.debug('Parsed row %s as %s\n', row, self._interest[-1])
