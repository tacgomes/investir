import logging
from datetime import date, datetime
from decimal import Decimal

from moneyed import Currency, Money

from investir.findata.dataprovider import (
    CacheMissError,
    HistoricalExchangeRateProvider,
    LiveExchangeRateProvider,
    ProviderError,
    SecurityInfoProvider,
)
from investir.findata.types import SecurityInfo
from investir.typing import ISIN

logger = logging.getLogger(__name__)


class FinancialData:
    def __init__(
        self,
        security_info_provider: SecurityInfoProvider | None,
        live_rates_provider: LiveExchangeRateProvider | None,
        historical_rates_provider: HistoricalExchangeRateProvider | None,
    ) -> None:
        self._security_info_provider = security_info_provider
        self._live_rates_provider = live_rates_provider
        self._historical_rates_provider = historical_rates_provider

    def get_security_info(
        self, isin: ISIN, name: str = "", refresh_date: datetime | None = None
    ) -> SecurityInfo:
        if self._security_info_provider is not None:
            try:
                return self._security_info_provider.get_info(isin, name, refresh_date)
            except CacheMissError:
                pass
            except ProviderError as ex:
                logger.warning(str(ex))

        return SecurityInfo(name, [])

    def get_security_price(self, isin, name: str = "") -> Money | None:
        if self._security_info_provider is not None:
            try:
                return self._security_info_provider.get_price(isin, name)
            except CacheMissError:
                pass
            except ProviderError as ex:
                logger.warning(str(ex))

        return None

    def get_exchange_rate(
        self, base: Currency, quote: Currency, rate_date: date | None = None
    ) -> Decimal | None:
        try:
            if rate_date is None and self._live_rates_provider is not None:
                return self._live_rates_provider.get_rate(base, quote)
            if rate_date is not None and self._historical_rates_provider is not None:
                return self._historical_rates_provider.get_rate(base, quote, rate_date)
        except CacheMissError:
            pass
        except ProviderError as ex:
            logger.warning(str(ex))

        return None

    def convert_money(
        self, money: Money, currency, rate_date: date | None = None
    ) -> Money | None:
        if money.currency == currency:
            return money

        if rate := self.get_exchange_rate(money.currency, currency, rate_date):
            return Money(money.amount * rate, currency)

        return None
