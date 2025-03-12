from datetime import date, datetime
from decimal import Decimal
from typing import Protocol

from moneyed import Currency, Money

from investir.exceptions import InvestirError
from investir.findata.types import SecurityInfo
from investir.typing import ISIN


class ProviderError(InvestirError):
    pass


class RequestError(ProviderError):
    pass


class DataNotFoundError(ProviderError):
    pass


class CacheMissError(ProviderError):
    pass


class SecurityInfoProvider(Protocol):
    def get_info(
        self, isin: ISIN, name: str = "", refresh_date: datetime | None = None
    ) -> SecurityInfo:
        pass

    def get_price(self, isin: ISIN, name: str = "") -> Money:
        pass


class LiveExchangeRateProvider(Protocol):
    def get_rate(self, base: Currency, quote: Currency) -> Decimal:
        pass


class HistoricalExchangeRateProvider(Protocol):
    def get_rate(self, base: Currency, quote: Currency, rate_date: date) -> Decimal:
        pass
