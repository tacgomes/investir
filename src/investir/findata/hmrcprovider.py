import json
import logging
import os
from codecs import iterdecode
from csv import DictReader
from datetime import date
from decimal import Decimal
from pathlib import Path
from urllib import request
from urllib.error import URLError

from moneyed import GBP, Currency

from investir.config import config
from investir.const import CURRENCY_CODES
from investir.findata.dataprovider import (
    CacheMissError,
    DataNotFoundError,
    RequestError,
)

logger = logging.getLogger(__name__)


TRADE_TARIFF_URL = (
    "https://www.trade-tariff.service.gov.uk/api/v2/exchange_rates/files/"
)


def date_to_key(d: date) -> str:
    return d.strftime("%Y-%m")


def date_to_filename(d: date) -> str:
    return f"monthly_csv_{d.strftime('%Y-%m')}.csv"


class HmrcMonthlyExhangeRateProvider:
    def __init__(self, cache_file: Path | None = None) -> None:
        self._cache: dict[str, dict[str, str]] = {}
        self._cache_file = cache_file or config.cache_dir / "hmrc-monthly-rates.json"
        self._cache_loaded = False

    def get_rate(self, base: Currency, quote: Currency, rate_date: date) -> Decimal:
        self._load_cache()

        if rate := self._find_rate(base, quote, rate_date):
            return rate

        if config.offline:
            raise CacheMissError

        filename = date_to_filename(rate_date)
        url = f"{TRADE_TARIFF_URL}{filename}"
        key = date_to_key(rate_date)

        try:
            with request.urlopen(url) as response:
                charset = response.info().get_content_charset()
                for row in DictReader(iterdecode(response, charset)):
                    currency_code = row["Currency Code"]
                    currency_rate = row["Currency Units per £1"]
                    if currency_code in CURRENCY_CODES:
                        self._cache.setdefault(key, {})[currency_code] = currency_rate
        except URLError as e:
            logger.debug("Exception from urllib: %s", repr(e))
            raise RequestError(
                f"Failed to fetch exchange rates file ({filename}): {e}"
            ) from None

        self._save_cache()

        if (rate := self._find_rate(base, quote, rate_date)) is None:
            raise DataNotFoundError(
                f"Exchange rate not found: {base.code}-{quote.code}"
            )

        return rate

    def _find_rate(
        self, base: Currency, quote: Currency, rate_date: date
    ) -> Decimal | None:
        key = date_to_key(rate_date)
        rates = self._cache.get(key, {})

        if base == GBP:
            if rate := rates.get(quote.code):
                return Decimal(rate)
        elif quote == GBP:
            if rate := rates.get(base.code):
                return Decimal("1.0") / Decimal(rate)
        else:
            raise ValueError("Either 'base' or 'quote' must be 'GBP'")

        return None

    def _save_cache(self) -> None:
        self._cache_file.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self._cache_file.parent / (self._cache_file.name + ".tmp")

        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump(self._cache, f, indent=4, sort_keys=True)

        os.replace(tmp_path, self._cache_file)

    def _load_cache(self) -> None:
        if not self._cache_loaded and self._cache_file.exists():
            logger.info("Loading historical exchange rates from %s", self._cache_file)
            with self._cache_file.open(encoding="utf-8") as f:
                self._cache = json.load(f)

        self._cache_loaded = True
