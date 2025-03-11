import logging
from csv import DictReader
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Final

from moneyed import Currency

from investir.const import BASE_CURRENCY
from investir.findata.dataprovider import DataNotFoundError, ProviderError

logger = logging.getLogger(__name__)


FIELDS: Final = ["Date", "Currency", "Rate"]


class LocalHistoricalExchangeRateProvider:
    def __init__(self, rates_file: Path) -> None:
        self._rates: dict[date, dict[Currency, Decimal]] = {}

        self._load_rates(rates_file)

    def get_rate(self, base: Currency, quote: Currency, rate_date: date) -> Decimal:
        if rate := self._find_rate(base, quote, rate_date):
            return rate

        raise DataNotFoundError(f"Exchange rate not found: {base.code}-{quote.code}")

    def _find_rate(
        self, base: Currency, quote: Currency, rate_date: date
    ) -> Decimal | None:
        rates = self._rates.get(rate_date, {})

        if base == BASE_CURRENCY:
            if rate := rates.get(quote):
                return Decimal(rate)
        elif quote == BASE_CURRENCY:
            if rate := rates.get(base):
                return Decimal("1.0") / Decimal(rate)
        else:
            raise ValueError(f"Either 'base' or 'quote' must be '{BASE_CURRENCY}'")

        return None

    def _load_rates(self, rates_file: Path) -> None:
        logger.info("Loading historical exchange rates from %s", rates_file)
        with rates_file.open(encoding="utf-8") as file:
            reader = DictReader(file)

            if reader.fieldnames != FIELDS:
                raise ProviderError("Exchange rates file is invalid")

            for row in reader:
                rate_date = date.fromisoformat(row["Date"])
                currency_code = Currency(row["Currency"])
                currency_rate = Decimal(row["Rate"])
                self._rates.setdefault(rate_date, {})[currency_code] = currency_rate
