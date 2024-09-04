from abc import ABC, abstractmethod
from decimal import Decimal

import yfinance

from .securitydata import SecurityData, Split
from .typing import ISIN


class SecuritiesDataProvider(ABC):
    @staticmethod
    @abstractmethod
    def name() -> str:
        pass

    @abstractmethod
    def get_security_data(self, isin: ISIN) -> SecurityData:
        pass


class NoopDataProvider(SecuritiesDataProvider):
    @staticmethod
    def name() -> str:
        return "Noop"

    def get_security_data(self, _isin: ISIN) -> SecurityData:
        return SecurityData("", [])


class YahooFinanceDataProvider(SecuritiesDataProvider):
    @staticmethod
    def name() -> str:
        return "Yahoo Finance"

    def get_security_data(self, isin: ISIN) -> SecurityData:
        try:
            yf_data = yfinance.Ticker(isin)
            name = yf_data.info["shortName"]
        except yfinance.exceptions.YFException:
            return SecurityData("", [])

        splits = [
            Split(pd_date.to_pydatetime(), Decimal(ratio))
            for pd_date, ratio in yf_data.splits.items()
        ]

        return SecurityData(name, splits)
