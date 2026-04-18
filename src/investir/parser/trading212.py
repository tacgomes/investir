import logging
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Final

from dateutil.parser import parse as parse_timestamp
from moneyed import Money

from investir.const import MIN_TIMESTAMP
from investir.exceptions import (
    CalculatedAmountError,
    FeesError,
    OrderDateError,
    ParseError,
    TransactionUnknownError,
)
from investir.fees import Fees
from investir.parser.factory import ParserFactory
from investir.parser.parser import Field as F
from investir.parser.parser import ParserBase, ParsingResult, Row
from investir.transaction import (
    Acquisition,
    Disposal,
    Dividend,
    Interest,
    Order,
    Transfer,
)
from investir.typing import ISIN, Ticker
from investir.utils import money, raise_or_warn, read_decimal

logger = logging.getLogger(__name__)


def read_monetary_field(row: Row, amount_field: str) -> Money | None:
    if amount := row.data.get(amount_field, "").strip():
        currency_field = f"Currency ({amount_field})"
        return money(amount=amount, currency=row[currency_field])

    if amount := row.data.get(f"{amount_field} (GBP)", "").strip():
        return money(amount=amount, currency="GBP")

    return None


@ParserFactory.register("Trading212")
class Trading212Parser(ParserBase):
    SCHEMA: Final = (
        F("Action", required=True),
        F("Time", required=True),
        F("Notes"),
        F("ID"),
        F("ISIN"),
        F("Ticker"),
        F("Name"),
        F("No. of shares"),
        F("Price / share"),
        F("Currency (Price / share)"),
        F("Exchange rate"),
        F("Total"),
        F("Currency (Total)"),
        # Dividend
        F("Withholding tax"),
        F("Currency (Withholding tax)"),
        # Fees
        F("Stamp duty"),
        F("Currency (Stamp duty)"),
        F("Stamp duty reserve tax"),
        F("Currency (Stamp duty reserve tax)"),
        F("Currency conversion fee"),
        F("Currency (Currency conversion fee)"),
        F("Finra fee"),
        F("Currency (Finra fee)"),
        F("Transaction fee"),
        F("Currency (Transaction fee)"),
        # Legacy
        F("Stamp duty (GBP)"),
        F("Stamp duty reserve tax (GBP)"),
        F("Total (GBP)"),
        F("Currency conversion fee (GBP)"),
        F("Transaction fee (GBP)"),
        F("Finra fee (GBP)"),
        # Not used
        F("Result"),
        F("Currency (Result)"),
        F("Charge amount (GBP)"),
        F("Deposit fee (GBP)"),
        F("Currency conversion from amount"),
        F("Currency (Currency conversion from amount)"),
        F("Currency conversion to amount"),
        F("Currency (Currency conversion to amount)"),
        F("Merchant name"),
        F("Merchant category"),
    )

    def __init__(self, csv_file: Path) -> None:
        super().__init__(csv_file, self.SCHEMA)

    def can_parse(self) -> bool:
        return super().can_parse() and (
            "Total" in self.field_names or "Total (GBP)" in self.field_names
        )

    def parse(self) -> ParsingResult:
        parse_fn = {
            "Market buy": self._parse_order,
            "Limit buy": self._parse_order,
            "Stop buy": self._parse_order,
            "Stop limit buy": self._parse_order,
            "Market sell": self._parse_order,
            "Limit sell": self._parse_order,
            "Stop sell": self._parse_order,
            "Stop limit sell": self._parse_order,
            "Dividend (Ordinary)": self._parse_dividend,
            "Dividend (Dividend)": self._parse_dividend,
            "Dividend (Dividends paid by us corporations)": self._parse_dividend,
            "Dividend (Dividends paid by foreign corporations)": self._parse_dividend,
            "Dividend (Dividend manufactured payment)": self._parse_dividend,
            "Deposit": self._parse_transfer,
            "Withdrawal": self._parse_transfer,
            "Interest on cash": self._parse_interest,
            "Lending interest": self._parse_interest,
            "Stock split open": None,
            "Stock split close": None,
            "Result adjustment": None,
            "Card debit": None,
            "Spending cashback": None,
            "Currency conversion": None,
        }

        self.validate_fields()

        for row in self.rows():
            tr_type = row["Action"]

            if tr_type not in parse_fn:
                raise_or_warn(
                    TransactionUnknownError(self._csv_file, row.data, tr_type)
                )
                continue

            if fn := parse_fn.get(tr_type):
                timestamp = parse_timestamp(row["Time"])
                tr_id = row["ID"]

                if timestamp.tzinfo is None:
                    timestamp = timestamp.replace(tzinfo=timezone.utc)

                if (total := read_monetary_field(row, "Total")) is not None:
                    fn(row, tr_type, timestamp, tr_id, total)

        return self.parsing_result()

    def _parse_order(
        self,
        row: Row,
        tr_type: str,
        timestamp: datetime,
        tr_id: str,
        total: Money,
    ) -> None:
        isin = row["ISIN"]
        ticker = row["Ticker"]
        name = row["Name"]
        num_shares = Decimal(row["No. of shares"])
        price_share = Decimal(row["Price / share"])
        exchange_rate = read_decimal(row["Exchange rate"], default=Decimal("1.0"))

        stamp_duty = read_monetary_field(row, "Stamp duty")
        stamp_duty_reserve_tax = read_monetary_field(row, "Stamp duty reserve tax")
        forex_fee = read_monetary_field(row, "Currency conversion fee")
        sec_fee = read_monetary_field(row, "Transaction fee")
        finra_fee = read_monetary_field(row, "Finra fee")

        if timestamp < MIN_TIMESTAMP:
            raise OrderDateError(self._csv_file, row.data)

        if stamp_duty and stamp_duty_reserve_tax:
            raise FeesError(
                self._csv_file,
                row.data,
                "Stamp duty (GBP)",
                "Stamp duty reserve tax (GBP)",
            )

        stamp_duty = stamp_duty or stamp_duty_reserve_tax

        if stamp_duty and finra_fee:
            raise FeesError(self._csv_file, row.data, "Stamp duty (GBP)", "Finra fee")

        if stamp_duty and sec_fee:
            raise FeesError(
                self._csv_file, row.data, "Stamp duty (GBP)", "Transaction fee"
            )

        fees = Fees(
            stamp_duty=stamp_duty,
            forex=forex_fee,
            finra=finra_fee,
            sec=sec_fee,
            default_currency=total.currency,
        )

        # NB: If one of the fees is in a currency different than the currency
        # for the total or the currency for any other fee that also applies, a
        # TypeError exception will be raised below. This is not something
        # expected to happen but it is good to be prepared for that eventuality
        # instead of silently ignore it.

        order_class: type[Order] = Acquisition
        fees_total = fees.total

        if tr_type in ("Market sell", "Limit sell", "Stop sell", "Stop limit sell"):
            order_class = Disposal
            fees_total *= -1

        calculated_total = (
            Money(price_share * num_shares / exchange_rate, total.currency) + fees_total
        ).round(2)

        if abs(calculated_total - total).amount > Decimal("0.01"):
            raise_or_warn(
                CalculatedAmountError(
                    self._csv_file, row.data, total.amount, calculated_total.amount
                )
            )

        self.add_order(
            order_class(
                timestamp,
                isin=ISIN(isin),
                ticker=Ticker(ticker),
                name=name,
                total=total,
                quantity=num_shares,
                fees=fees,
                tr_id=tr_id,
            ),
            row,
        )

    def _parse_dividend(
        self,
        row: Row,
        tr_type: str,
        timestamp: datetime,
        tr_id: str,
        total: Money,
    ):
        isin = row["ISIN"]
        ticker = row["Ticker"]
        name = row["Name"]
        withholding_tax = read_decimal(row["Withholding tax"])
        currency_withholding_tax = row["Currency (Withholding tax)"]
        forex_fee = read_monetary_field(row, "Currency conversion fee")

        if forex_fee:
            raise ParseError(self._csv_file, row.data, "Dividend with conversion fee")

        self.add_dividend(
            Dividend(
                timestamp,
                isin=ISIN(isin),
                ticker=Ticker(ticker),
                name=name,
                total=total,
                withheld=money(withholding_tax, currency_withholding_tax),
                tr_id=tr_id,
            ),
            row,
        )

    def _parse_transfer(
        self,
        row: Row,
        tr_type: str,
        timestamp: datetime,
        tr_id: str,
        total: Money,
    ):
        if tr_type == "Withdrawal":
            total = -abs(total)

        self.add_transfer(Transfer(timestamp, tr_id=tr_id, total=total), row)

    def _parse_interest(
        self,
        row: Row,
        tr_type: str,
        timestamp: datetime,
        tr_id: str,
        total: Money,
    ):
        self.add_interest(Interest(timestamp, tr_id=tr_id, total=total), row)
