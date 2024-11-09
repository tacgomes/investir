import logging
from decimal import Decimal
from pathlib import Path
from typing import Final

import yaml
from iso4217 import Currency

from investir.findata.dataprovider import (
    DataProviderError,
    ExchangeRateProvider,
    SecurityInfoProvider,
)
from investir.findata.types import Price, SecurityInfo
from investir.trhistory import TrHistory
from investir.typing import ISIN

logger = logging.getLogger(__name__)


class FinancialData:
    VERSION: Final = 1

    def __init__(
        self,
        security_info_provider: SecurityInfoProvider | None,
        exchange_rate_provider: ExchangeRateProvider | None,
        tr_hist: TrHistory,
        cache_file: Path,
    ) -> None:
        self._security_info_provider = security_info_provider
        self._exchange_rate_provider = exchange_rate_provider
        self._tr_hist = tr_hist
        self._cache_file = cache_file
        self._security_info: dict[ISIN, SecurityInfo] = {}
        self._security_price: dict[ISIN, Price] = {}
        self._exchange_rates: dict[tuple[Currency, Currency], Decimal] = {}

        self._initialise()

    def get_security_info(self, isin: ISIN) -> SecurityInfo:
        return self._security_info[isin]

    def get_security_price(self, isin) -> Price | None:
        if price := self._security_price.get(isin):
            return price

        if self._security_info_provider is not None:
            try:
                price = self._security_info_provider.fetch_price(isin)
                logger.debug(
                    "Using %s %s share price for %s",
                    round(price.amount, 2),
                    price.currency.code,
                    isin,
                )
                self._security_price[isin] = price
            except DataProviderError as ex:
                logger.warning(str(ex))

        return price

    def get_foreign_exchange_rate(
        self, currency_from: Currency, currency_to: Currency
    ) -> Decimal | None:
        if fx_rate := self._exchange_rates.get((currency_from, currency_to)):
            return fx_rate

        if self._exchange_rate_provider is not None:
            try:
                fx_rate = self._exchange_rate_provider.fetch_exchange_rate(
                    currency_from, currency_to
                )
                inverse_fx_rate = Decimal("1.0") / fx_rate
                logger.debug(
                    "Using %s exchange rate for %s (%s) to %s (%s) (inverse rate: %s)",
                    round(fx_rate, 5),
                    currency_from.currency_name,
                    currency_from.code,
                    currency_to.currency_name,
                    currency_to.code,
                    round(inverse_fx_rate, 5),
                )
                self._exchange_rates[(currency_from), (currency_to)] = fx_rate
                self._exchange_rates[(currency_to), (currency_from)] = inverse_fx_rate
            except DataProviderError as ex:
                logger.warning(str(ex))

        return fx_rate

    def convert_currency(
        self,
        amount: Decimal,
        currency_from: Currency,
        currency_to: Currency = Currency.GBP,  # type: ignore[attr-defined]
    ) -> Decimal | None:
        if currency_from == currency_to:
            return amount

        if fx_rate := self.get_foreign_exchange_rate(currency_from, currency_to):
            return amount * fx_rate

        return None

    def _initialise(self) -> None:
        self._load_cache()

        orders = self._tr_hist.orders
        update_cache = False

        for isin, name in self._tr_hist.securities:
            if (security_info := self._security_info.get(isin)) is not None:
                last_order = next(o for o in reversed(orders) if o.isin == isin)

                if security_info.last_updated > last_order.timestamp:
                    logger.debug(
                        "Securities cache for %s (%s) is up-to-date", name, isin
                    )
                    continue

            self._security_info[isin] = SecurityInfo(name, [])
            update_cache = True

            if self._security_info_provider is not None:
                logger.info("Fetching information for %s - %s", isin, name)
                try:
                    self._security_info[isin] = self._security_info_provider.fech_info(
                        isin
                    )
                except DataProviderError as ex:
                    logger.warning(str(ex))

        if update_cache:
            self._update_cache()

    def _load_cache(self) -> None:
        if self._cache_file.exists():
            logger.info("Loading securities cache from %s", self._cache_file)

            with self._cache_file.open("r") as file:
                if data := yaml.load(file, Loader=yaml.FullLoader):
                    self._security_info = data["securities"]

    def _update_cache(self) -> None:
        if self._cache_file.exists():
            logger.info("Updating securities cache on %s", self._cache_file)
        else:
            logger.info("Creating securities cache on %s", self._cache_file)

        self._cache_file.parent.mkdir(parents=True, exist_ok=True)
        securities_info = dict(sorted(self._security_info.items()))
        data = {"version": self.__class__.VERSION, "securities": securities_info}

        with self._cache_file.open("w") as file:
            yaml.dump(data, file, sort_keys=False)
