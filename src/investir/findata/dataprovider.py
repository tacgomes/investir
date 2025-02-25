from decimal import Decimal
from typing import Protocol

from moneyed import Currency, Money

from investir.findata.types import SecurityInfo
from investir.typing import ISIN


class DataProviderError(Exception):
    pass


class SecurityInfoProvider(Protocol):
    def get_info(self, isin: ISIN) -> SecurityInfo:
        pass

    def get_price(self, isin: ISIN) -> Money:
        pass


class LiveExchangeRateProvider(Protocol):
    def get_rate(self, base: Currency, quote: Currency) -> Decimal:
        pass
