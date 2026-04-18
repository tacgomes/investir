import logging
from datetime import datetime
from decimal import ROUND_DOWN, Decimal
from pathlib import Path
from typing import Final

from dateutil.parser import parse as parse_timestamp
from moneyed import GBP, Money

from investir.const import MIN_TIMESTAMP
from investir.exceptions import (
    CalculatedAmountError,
    FeesError,
    InvestirError,
    OrderDateError,
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
    FreeShare,
    Interest,
    Order,
    Transfer,
)
from investir.typing import ISIN, Ticker
from investir.utils import money, raise_or_warn, read_decimal, read_sterling

logger = logging.getLogger(__name__)


@ParserFactory.register("Freetrade")
class FreetradeParser(ParserBase):
    SCHEMA: Final = (
        F("Title"),
        F("Type", required=True),
        F("Timestamp", required=True),
        F("Account Currency", required=True),
        F("Total Amount in Account Currency", "Total Amount", required=True),
        F("Buy / Sell"),
        F("Ticker"),
        F("ISIN"),
        F("Price per Share in Account Currency"),
        F("Stamp Duty"),
        F("Quantity"),
        F("Order ID"),
        F("Price per Share"),
        F("FX Rate"),
        F("Base FX Rate"),
        F("FX Fee Amount"),
        F("Dividend Eligible Quantity"),
        F("Dividend Amount Per Share"),
        F("Dividend Withheld Tax Percentage"),
        F("Dividend Withheld Tax Amount"),
        # Not used
        F("Venue"),
        F("Order Type"),
        F("Instrument Currency"),
        F("Total Amount in Instrument Currency", "Total Shares Amount"),
        F("FX Fee (BPS)"),
        F("Dividend Ex Date"),
        F("Dividend Pay Date"),
        F("Dividend Gross Distribution Amount"),
        F("Dividend Net Distribution Amount"),
        F("Stock Split Ex Date"),
        F("Stock Split Pay Date"),
        F("Stock Split New ISIN"),
        F("Stock Split Rate of Share Outturn From"),
        F("Stock Split Rate of Share Outturn To"),
        F("Stock Split Maintain Holding of Initial ISIN"),
        F("Stock Split New Share Quantity"),
        F("Stock Split Rate of Cash Outturn Amount"),
        F("Stock Split Rate of Cash Outturn Currency"),
        F("Stock Split Cash Outturn Received Amount"),
        F("Stock Split Has Fractional Payout"),
        F("Stock Split Rate of Fractional Payout Amount"),
        F("Stock Split Rate of Fractional Payout Currency"),
        F("Stock Split Fractional Payout Cash Received Amount"),
        F("Stock Split Fractional Payout Cash Received Currency"),
    )

    def __init__(self, csv_file: Path) -> None:
        super().__init__(csv_file, self.SCHEMA)

    def parse(self) -> ParsingResult:
        parse_fn = {
            "ORDER": self._parse_order,
            "FREESHARE_ORDER": self._parse_free_share,
            "DIVIDEND": self._parse_dividend,
            "TOP_UP": self._parse_transfer,
            "WITHDRAWAL": self._parse_transfer,
            "INTERNAL_TRANSFER": self._parse_internal_transfer,
            "INTEREST_FROM_CASH": self._parse_interest,
            "MONTHLY_STATEMENT": None,
            "TAX_CERTIFICATE": None,
        }

        self.validate_fields()

        # Freetrade transactions are ordered from most recent to
        # oldest but we want the order ID to increase from the
        # oldest to the most recent.
        for row in self.rows(reverse=True):
            tr_type = row["Type"]

            if tr_type not in parse_fn:
                raise_or_warn(
                    TransactionUnknownError(self._csv_file, row.data, tr_type)
                )
                continue

            if fn := parse_fn.get(tr_type):
                timestamp = parse_timestamp(row["Timestamp"])
                total = money(
                    row["Total Amount in Account Currency"], row["Account Currency"]
                )

                fn(row, tr_type, timestamp, total)

        return self.parsing_result()

    def _parse_order(
        self,
        row: Row,
        tr_type: str,
        timestamp: datetime,
        total: Money,
    ) -> None:
        title = row["Title"]
        action = row["Buy / Sell"]
        ticker = row["Ticker"]
        isin = row["ISIN"]
        price = Decimal(row["Price per Share in Account Currency"])
        quantity = Decimal(row["Quantity"])
        order_id = row["Order ID"]
        stamp_duty = read_sterling(row["Stamp Duty"])
        fx_fee = read_sterling(row["FX Fee Amount"])

        if action not in ("BUY", "SELL"):
            raise TransactionUnknownError(self._csv_file, row.data, action)

        if timestamp < MIN_TIMESTAMP:
            raise OrderDateError(self._csv_file, row.data)

        if stamp_duty and fx_fee:
            raise FeesError(self._csv_file, row.data, "Stamp Duty", "FX Fee Amount")

        fees = Fees(
            stamp_duty=stamp_duty, forex=fx_fee, default_currency=total.currency
        )

        order_class: type[Order] = Acquisition
        fees_total = fees.total

        if action == "SELL":
            order_class = Disposal
            fees_total *= -1

        calculated_total = (Money(price * quantity, GBP) + fees_total).round(2)
        if calculated_total != total:
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
                name=title,
                total=total,
                quantity=quantity,
                fees=fees,
                tr_id=order_id,
            ),
            row,
        )

    def _parse_free_share(
        self,
        row: Row,
        tr_type: str,
        timestamp: datetime,
        total: Money,
    ) -> None:
        title = row["Title"]
        ticker = row["Ticker"]
        isin = row["ISIN"]
        quantity = Decimal(row["Quantity"])
        order_id = row["Order ID"]

        # Free shares should have zero cost (total should be zero or close to zero)
        # but we accept the actual total from the CSV in case there are any fees
        self.add_order(
            FreeShare(
                timestamp,
                isin=ISIN(isin),
                ticker=Ticker(ticker),
                name=title,
                total=total,
                quantity=quantity,
                fees=Fees(default_currency=total.currency),
                tr_id=order_id,
            ),
            row,
        )

    def _parse_dividend(
        self,
        row: Row,
        tr_type: str,
        timestamp: datetime,
        total: Money,
    ):
        title = row["Title"]
        ticker = row["Ticker"]
        isin = row["ISIN"]
        base_fx_rate = read_decimal(row["Base FX Rate"], Decimal("1.0"))
        eligible_quantity = Decimal(row["Dividend Eligible Quantity"])
        amount_per_share = Decimal(row["Dividend Amount Per Share"])
        withheld_tax_percentage = Decimal(row["Dividend Withheld Tax Percentage"])
        withheld_tax_amount = Decimal(row["Dividend Withheld Tax Amount"])

        calculated_total = (
            amount_per_share
            * eligible_quantity
            * ((Decimal("100") - withheld_tax_percentage) / 100)
            * base_fx_rate
        )

        calculated_total = calculated_total.quantize(
            Decimal("1.00"), rounding=ROUND_DOWN
        )

        # Freetrade does not seem to use a consistent method for rounding dividends.
        # Thus, allow the calculated amount to differ by one pence.
        # https://community.freetrade.io/t/dividend-amount-off-by-one-penny/71806/7
        if abs(total.amount - calculated_total) > Decimal("0.01"):
            raise_or_warn(
                CalculatedAmountError(
                    self._csv_file, row.data, total.amount, calculated_total
                )
            )

        self.add_dividend(
            Dividend(
                timestamp,
                isin=ISIN(isin),
                ticker=Ticker(ticker),
                name=title,
                total=total,
                withheld=Money(withheld_tax_amount * base_fx_rate, total.currency),
            ),
            row,
        )

    def _parse_transfer(
        self,
        row: Row,
        tr_type: str,
        timestamp: datetime,
        total: Money,
    ):
        if tr_type == "WITHDRAWAL":
            total = -abs(total)

        self.add_transfer(Transfer(timestamp, total), row)

    def _parse_internal_transfer(
        self,
        row: Row,
        tr_type: str,
        timestamp: datetime,
        total: Money,
    ):
        title = row["Title"]
        # Check if transfer is "to" an account (outbound) or "from" an account (inbound)
        # "Internal Transfer to ISA" -> negative (money leaving)
        # "Internal Transfer from GIA" -> positive (money coming in)
        if title.startswith("Internal Transfer from"):
            pass
        elif title.startswith("Internal Transfer to"):
            total = -abs(total)
        else:
            raise_or_warn(InvestirError(f"Unknown internal transfer type: {title}"))

        self.add_transfer(Transfer(timestamp, total), row)

    def _parse_interest(
        self,
        row: Row,
        tr_type: str,
        timestamp: datetime,
        total: Money,
    ):
        self.add_interest(Interest(timestamp, total), row)
