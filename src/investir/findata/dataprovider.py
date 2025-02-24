from decimal import Decimal
from typing import Protocol

from moneyed import Currency, Money

from investir.findata.types import SecurityInfo
from investir.typing import ISIN


class DataProviderError(Exception):
    pass


class SecurityInfoProvider(Protocol):
    def fech_info(self, isin: ISIN) -> SecurityInfo:
        pass

    def fetch_price(self, isin: ISIN) -> Money:
        pass


class LiveExchangeRateProvider(Protocol):
    def fetch_exchange_rate(
        self, currency_from: Currency, currency_to: Currency
    ) -> Decimal:
        pass
