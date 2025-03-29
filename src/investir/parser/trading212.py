import logging
from collections.abc import Mapping
from csv import DictReader
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
    FieldUnknownError,
    OrderDateError,
    ParseError,
    TransactionTypeError,
)
from investir.fees import Fees
from investir.parser.factory import ParserFactory
from investir.parser.types import ParsingResult
from investir.transaction import (
    Acquisition,
    Disposal,
    Dividend,
    Interest,
    Order,
    Transfer,
)
from investir.typing import ISIN, Ticker
from investir.utils import dict2str, raise_or_warn, read_decimal, read_sterling

logger = logging.getLogger(__name__)


def read_money(row: Mapping[str, str], amount_field: str) -> Money | None:
    if amount := row.get(amount_field, "").strip():
        return Money(amount=amount, currency=row[f"Currency ({amount_field})"])

    if amount := row.get(f"{amount_field} (GBP)", "").strip():
        return Money(amount=amount, currency="GBP")

    return None


@ParserFactory.register("Trading212")
class Trading212Parser:
    FIELDS: Final = (
        "Action",
        "Time",
        "Notes",
        "ID",
        "ISIN",
        "Ticker",
        "Name",
        "No. of shares",
        "Price / share",
        "Currency (Price / share)",
        "Exchange rate",
        "Total",
        "Currency (Total)",
        # Dividend
        "Withholding tax",
        "Currency (Withholding tax)",
        # Fees
        "Stamp duty (GBP)",
        "Stamp duty reserve tax (GBP)",
        "Currency conversion fee",
        "Currency (Currency conversion fee)",
        "Finra fee",
        "Currency (Finra fee)",
        "Transaction fee",
        "Currency (Transaction fee)",
        # Legacy
        "Total (GBP)",
        "Currency conversion fee (GBP)",
        "Transaction fee (GBP)",
        "Finra fee (GBP)",
        # Ignored
        "Result",
        "Currency (Result)",
        "Charge amount (GBP)",
        "Deposit fee (GBP)",
        "Currency conversion from amount",
        "Currency (Currency conversion from amount)",
        "Currency conversion to amount",
        "Currency (Currency conversion to amount)",
        "Merchant name",
        "Merchant category",
    )

    def __init__(self, csv_file: Path) -> None:
        self._csv_file = csv_file
        self._orders: list[Order] = []
        self._dividends: list[Dividend] = []
        self._transfers: list[Transfer] = []
        self._interest: list[Interest] = []

    def can_parse(self) -> bool:
        with self._csv_file.open(encoding="utf-8") as file:
            reader = DictReader(file)
            fieldnames = reader.fieldnames or []

        if "Action" not in fieldnames or "Time" not in fieldnames:
            return False

        if "Total" not in fieldnames and "Total (GBP)" not in fieldnames:
            return False

        return True

    def parse(self) -> ParsingResult:
        parse_fn = {
            "Market buy": self._parse_order,
            "Limit buy": self._parse_order,
            "Stop buy": self._parse_order,
            "Market sell": self._parse_order,
            "Limit sell": self._parse_order,
            "Stop sell": self._parse_order,
            "Dividend (Ordinary)": self._parse_dividend,
            "Dividend (Dividend)": self._parse_dividend,
            "Dividend (Dividends paid by us corporations)": self._parse_dividend,
            "Dividend (Dividends paid by foreign corporations)": self._parse_dividend,
            "Deposit": self._parse_transfer,
            "Withdrawal": self._parse_transfer,
            "Interest on cash": self._parse_interest,
            "Lending interest": self._parse_interest,
            "Result adjustment": None,
            "Card debit": None,
            "Spending cashback": None,
            "Currency conversion": None,
        }

        with self._csv_file.open(encoding="utf-8") as file:
            reader = DictReader(file)

            unknown_fields = [
                f for f in reader.fieldnames or [] if f not in self.FIELDS
            ]
            if unknown_fields:
                raise_or_warn(FieldUnknownError(unknown_fields))

            for row in reader:
                tr_type = row["Action"]

                if tr_type not in parse_fn:
                    raise_or_warn(TransactionTypeError(self._csv_file, row, tr_type))
                    continue

                if fn := parse_fn.get(tr_type):
                    timestamp = parse_timestamp(row["Time"])
                    tr_id = row["ID"]

                    if timestamp.tzinfo is None:
                        timestamp = timestamp.replace(tzinfo=timezone.utc)

                    if (total := read_money(row, "Total")) is not None:
                        fn(row, tr_type, timestamp, tr_id, total)

        return ParsingResult(
            self._orders, self._dividends, self._transfers, self._interest
        )

    def _parse_order(
        self,
        row: Mapping[str, str],
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

        # TODO: The PTM levy fee and the French Financial Transaction
        #       Tax (FRR) fee are not parsed as it is unclear what their
        #       field titles would be in the CSV. The list of possible
        #       fees is available at:
        #       https://helpcentre.trading212.com/hc/en-us/articles/360007081637-What-are-the-applicable-stock-exchange-fees
        stamp_duty = read_sterling(row.get("Stamp duty (GBP)"))
        stamp_duty_reserve_tax = read_sterling(row.get("Stamp duty reserve tax (GBP)"))
        forex_fee = read_money(row, "Currency conversion fee")
        sec_fee = read_money(row, "Transaction fee")
        finra_fee = read_money(row, "Finra fee")

        if timestamp < MIN_TIMESTAMP:
            raise OrderDateError(self._csv_file, row)

        if stamp_duty and stamp_duty_reserve_tax:
            raise FeesError(
                self._csv_file, row, "Stamp duty (GBP)", "Stamp duty reserve tax (GBP)"
            )

        stamp_duty = stamp_duty or stamp_duty_reserve_tax

        if stamp_duty and finra_fee:
            raise FeesError(self._csv_file, row, "Stamp duty (GBP)", "Finra fee")

        if stamp_duty and sec_fee:
            raise FeesError(self._csv_file, row, "Stamp duty (GBP)", "Transaction fee")

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

        if tr_type in ("Market sell", "Limit sell", "Stop sell"):
            order_class = Disposal
            fees_total *= -1

        calculated_total = (
            Money(price_share * num_shares / exchange_rate, total.currency) + fees_total
        ).round(2)

        if abs(calculated_total - total).amount > Decimal("0.01"):
            raise_or_warn(
                CalculatedAmountError(
                    self._csv_file, row, total.amount, calculated_total.amount
                )
            )

        self._orders.append(
            order_class(
                timestamp,
                isin=ISIN(isin),
                ticker=Ticker(ticker),
                name=name,
                total=total,
                quantity=num_shares,
                fees=fees,
                tr_id=tr_id,
            )
        )

        logger.debug("Parsed row %s as %s\n", dict2str(row), self._orders[-1])

    def _parse_dividend(
        self,
        row: Mapping[str, str],
        tr_type: str,
        timestamp: datetime,
        tr_id: str,
        total: Money,
    ):
        isin = row["ISIN"]
        ticker = row["Ticker"]
        name = row["Name"]
        currency_price_share = row["Currency (Price / share)"]
        withholding_tax = read_decimal(row["Withholding tax"])
        currency_withholding_tax = row["Currency (Withholding tax)"]
        fx_conversion_fee = row["Currency conversion fee"]

        if fx_conversion_fee:
            raise ParseError(self._csv_file, row, "Dividend with conversion fee")

        if currency_price_share != currency_withholding_tax:
            raise ParseError(
                self._csv_file,
                row,
                "Currency is different for share price and tax withheld",
            )

        self._dividends.append(
            Dividend(
                timestamp,
                isin=ISIN(isin),
                ticker=Ticker(ticker),
                name=name,
                total=total,
                withheld=Money(withholding_tax, currency_withholding_tax),
                tr_id=tr_id,
            )
        )

        logger.debug("Parsed row %s as %s\n", dict2str(row), self._dividends[-1])

    def _parse_transfer(
        self,
        row: Mapping[str, str],
        tr_type: str,
        timestamp: datetime,
        tr_id: str,
        total: Money,
    ):
        if tr_type == "Withdrawal":
            total = -abs(total)

        self._transfers.append(Transfer(timestamp, tr_id=tr_id, total=total))

        logger.debug("Parsed row %s as %s\n", dict2str(row), self._transfers[-1])

    def _parse_interest(
        self,
        row: Mapping[str, str],
        tr_type: str,
        timestamp: datetime,
        tr_id: str,
        total: Money,
    ):
        self._interest.append(Interest(timestamp, tr_id=tr_id, total=total))

        logger.debug("Parsed row %s as %s\n", dict2str(row), self._interest[-1])
