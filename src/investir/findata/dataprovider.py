import logging
from decimal import Decimal
from typing import Protocol

import yfinance
from iso4217 import Currency

from investir.findata.types import Price, SecurityInfo, Split
from investir.typing import ISIN

logger = logging.getLogger(__name__)


class DataProviderError(Exception):
    pass


class SecurityInfoProvider(Protocol):
    def fech_info(self, isin: ISIN) -> SecurityInfo:
        pass

    def fetch_price(self, isin: ISIN) -> Price:
        pass


class ExchangeRateProvider(Protocol):
    def fetch_exchange_rate(
        self, currency_from: Currency, currency_to: Currency
    ) -> Decimal:
        pass


class YahooFinanceSecurityInfoProvider:
    def fech_info(self, isin: ISIN) -> SecurityInfo:
        try:
            yf_data = yfinance.Ticker(isin)
            name = yf_data.info["shortName"]
        except Exception as ex:
            logger.debug("Exception from yfinance: %s", repr(ex))
            raise DataProviderError(f"Failed to fetch information for {isin}") from None

        splits = [
            Split(pd_date.to_pydatetime(), Decimal(ratio))
            for pd_date, ratio in yf_data.splits.items()
        ]

        return SecurityInfo(name, splits)

    def fetch_price(self, isin: ISIN) -> Price:
        try:
            yf_data = yfinance.Ticker(isin)
            price = Decimal(yf_data.info["currentPrice"])
            currency = yf_data.info["currency"]
        except Exception as e:
            logger.debug("Exception from yfinance: %s", repr(e))
            raise DataProviderError(
                f"Failed currency_to fetch last price for {isin}"
            ) from None

        if currency == "GBp":
            currency = "GBP"
            price *= Decimal("0.01")

        return Price(price, Currency(currency))


class YahooFinanceExchangeRateProvider(ExchangeRateProvider):
    def fetch_exchange_rate(
        self, currency_from: Currency, currency_to: Currency
    ) -> Decimal:
        try:
            yf_data = yfinance.Ticker(f"{currency_from.code}{currency_to.code}=X")
            fx_rate = Decimal(yf_data.info["bid"])
        except Exception as e:
            logger.debug("Exception from yfinance: %s", repr(e))
            raise DataProviderError(
                f"Failed to fetch exchange rate for "
                f"{currency_from.currency_name} ({currency_from.code}) to "
                f"{currency_to.currency_name} ({currency_to.code})"
            ) from None

        return fx_rate
