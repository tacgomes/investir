import json
import logging
import os
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import yaml
import yfinance
from moneyed import Currency, Money

from investir.config import config
from investir.findata.dataprovider import (
    CacheMissError,
    DataNotFoundError,
    RequestError,
)
from investir.findata.types import SecurityInfo, Split
from investir.typing import ISIN

logger = logging.getLogger(__name__)


def make_symbol(a: Currency, b: Currency) -> str:
    return f"{a.code}{b.code}=X"


class YahooFinanceSecurityInfoProvider:
    def __init__(self, cache_file: Path | None = None) -> None:
        self._cache_file = cache_file or config.cache_dir / "securities.yaml"
        self._cache_loaded = False
        self._infos: dict[ISIN, SecurityInfo] = {}
        self._prices: dict[ISIN, Money] = {}

    def get_info(
        self, isin: ISIN, name: str = "", refresh_date: datetime | None = None
    ) -> SecurityInfo:
        self._load_cache()

        if info := self._infos.get(isin):
            if refresh_date is None or info.last_updated >= refresh_date:
                return info

        if config.offline:
            raise CacheMissError

        logger.info("Fetching information for %s - %s", isin, name)

        try:
            yf_data = yfinance.Ticker(isin)
            name = yf_data.info["shortName"]
        except Exception as ex:
            logger.debug("Exception from yfinance: %s", repr(ex))
            raise RequestError(f"Failed to fetch information for {isin}") from None

        splits = [
            Split(pd_date.to_pydatetime(), Decimal(ratio))
            for pd_date, ratio in yf_data.splits.items()
        ]

        self._infos[isin] = SecurityInfo(name, splits)
        self._save_cache()

        return self._infos[isin]

    def get_price(self, isin: ISIN, name: str = "") -> Money:
        if cached_price := self._prices.get(isin):
            return cached_price

        if config.offline:
            raise CacheMissError

        logger.info("Fetching last price for %s - %s", isin, name)

        try:
            yf_data = yfinance.Ticker(isin)
            price = Decimal(yf_data.info["currentPrice"])
            currency = yf_data.info["currency"]
        except Exception as e:
            logger.debug("Exception from yfinance: %s", repr(e))
            raise RequestError(f"Failed to fetch last price for {isin}") from None

        if currency == "GBp":
            currency = "GBP"
            price *= Decimal("0.01")

        logger.debug(
            "Using %s %s share price for %s",
            round(price, 2),
            currency,
            isin,
        )

        self._prices[isin] = Money(price, currency)

        return self._prices[isin]

    def _save_cache(self) -> None:
        self._cache_file.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self._cache_file.parent / (self._cache_file.name + ".tmp")

        infos = dict(sorted(self._infos.items()))
        data = {"version": 1, "securities": infos}

        with tmp_path.open("w", encoding="utf-8") as f:
            yaml.dump(data, f, sort_keys=False)

        os.replace(tmp_path, self._cache_file)

    def _load_cache(self) -> None:
        if not self._cache_loaded and self._cache_file.exists():
            logger.info("Loading securities cache from %s", self._cache_file)
            with self._cache_file.open(encoding="utf-8") as f:
                if data := yaml.load(f, Loader=yaml.FullLoader):
                    self._infos = data["securities"]

        self._cache_loaded = True


class YahooFinanceLiveExchangeRateProvider:
    def __init__(self) -> None:
        self._rates: dict[tuple[Currency, Currency], Decimal] = {}

    def get_rate(self, base: Currency, quote: Currency) -> Decimal:
        if rate := self._rates.get((base, quote)):
            return rate

        if config.offline:
            raise CacheMissError

        try:
            yf_data = yfinance.Ticker(make_symbol(base, quote))
            rate = Decimal(yf_data.info["bid"])
        except Exception as e:
            logger.debug("Exception from yfinance: %s", repr(e))
            raise RequestError(
                f"Failed to fetch exchange rate for "
                f"{base.name} ({base.code}) to {quote.name} ({quote.code})"
            ) from None

        inverse_rate = Decimal("1.0") / rate
        logger.debug(
            "Using %s exchange rate for %s (%s) to %s (%s) (inverse rate: %s)",
            round(rate, 5),
            base.name,
            base.code,
            quote.name,
            quote.code,
            round(inverse_rate, 5),
        )

        self._rates[(base, quote)] = rate
        self._rates[(quote, base)] = inverse_rate

        return rate


class YahooFinanceHistoricalExchangeRateProvider:
    def __init__(self, cache_file: Path | None = None) -> None:
        self._cache: dict[str, dict[str, str]] = {}
        self._cache_file = cache_file or config.cache_dir / "yahoo-finance-rates.json"
        self._cache_loaded = False

    def get_rate(self, base: Currency, quote: Currency, rate_date: date) -> Decimal:
        self._load_cache()

        if rate := self._find_rate(base, quote, rate_date):
            return rate

        if config.offline:
            raise CacheMissError

        try:
            ticker = yfinance.Ticker(make_symbol(base, quote))
            rates = ticker.history(start=str(rate_date))
        except Exception as e:
            logger.debug("Exception from yfinance: %s", repr(e))
            raise RequestError(
                f"Failed to fetch exchange rate for "
                f"{base.name} ({base.code}) to "
                f"{quote.name} ({quote.code})"
            ) from None

        for timestamp, row in rates.iterrows():
            currency_pair = f"{base.code}-{quote.code}"
            date_key = str(timestamp.to_pydatetime().date())
            self._cache.setdefault(currency_pair, {})[date_key] = str(row["Close"])

        self._save_cache()

        if (rate := self._find_rate(base, quote, rate_date)) is None:
            raise DataNotFoundError(
                f"Exchange rate not found: {base.code}-{quote.code}"
            )

        return rate

    def _find_rate(
        self, base: Currency, quote: Currency, rate_date: date
    ) -> Decimal | None:
        if rates := self._cache.get(f"{base.code}-{quote.code}"):
            if rate := rates.get(str(rate_date)):
                return Decimal(rate)
        elif rates := self._cache.get(f"{quote.code}-{base.code}"):
            if rate := rates.get(str(rate_date)):
                return Decimal("1.0") / Decimal(rate)

        return None

    def _save_cache(self) -> None:
        self._cache_file.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self._cache_file.parent / (self._cache_file.name + ".tmp")

        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump(self._cache, f, indent=4)

        os.replace(tmp_path, self._cache_file)

    def _load_cache(self) -> None:
        if not self._cache_loaded and self._cache_file.exists():
            logger.info("Loading historical exchange rates from %s", self._cache_file)
            with self._cache_file.open(encoding="utf-8") as f:
                self._cache.update(json.load(f))

        self._cache_loaded = True
