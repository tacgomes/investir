import logging
from decimal import Decimal
from typing import Protocol

import yfinance

from investir.findata.types import SecurityData, Split
from investir.typing import ISIN

logger = logging.getLogger(__name__)


class SecuritiesDataProvider(Protocol):
    def get_security_data(self, isin: ISIN) -> SecurityData | None:
        pass


class NoopDataProvider:
    def get_security_data(self, _isin: ISIN) -> SecurityData:
        return SecurityData("", [])


class YahooFinanceDataProvider:
    def get_security_data(self, isin: ISIN) -> SecurityData | None:
        try:
            yf_data = yfinance.Ticker(isin)
            name = yf_data.info["shortName"]
        except Exception as e:
            logger.debug("Exception from yfinance: %s", str(e))
            return None

        splits = [
            Split(pd_date.to_pydatetime(), Decimal(ratio))
            for pd_date, ratio in yf_data.splits.items()
        ]

        return SecurityData(name, splits)
