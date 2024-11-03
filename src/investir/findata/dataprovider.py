import logging
from decimal import Decimal
from typing import Protocol

import yfinance

from investir.findata.types import SecurityInfo, Split
from investir.typing import ISIN

logger = logging.getLogger(__name__)


class DataProviderError(Exception):
    pass


class SecurityInfoProvider(Protocol):
    def fech_info(self, isin: ISIN) -> SecurityInfo:
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
