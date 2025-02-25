from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import pandas as pd
import pytest
import yfinance
from moneyed import GBP, USD, Money

from investir.findata import (
    DataProviderError,
    Split,
    YahooFinanceLiveExchangeRateProvider,
    YahooFinanceSecurityInfoProvider,
)
from investir.typing import ISIN

AMZN_PSERIES = pd.Series(
    data=[10.0, 3.0],
    index=[
        pd.Timestamp(2019, 1, 1, tzinfo=timezone.utc),
        pd.Timestamp(2021, 1, 1, tzinfo=timezone.utc),
    ],
)

AMZN_SPLITS = [
    Split(
        date_effective=datetime(2019, 1, 1, tzinfo=timezone.utc), ratio=Decimal("10.0")
    ),
    Split(
        date_effective=datetime(2021, 1, 1, tzinfo=timezone.utc), ratio=Decimal("3.0")
    ),
]


@pytest.fixture(name="ticker_info")
def _ticker_info(mocker) -> Callable:
    def _method(info: Mapping[str, Any] | Exception) -> None:
        return mocker.patch(
            "yfinance.Ticker.info",
            return_value=info,
            new_callable=mocker.PropertyMock,
        )

    return _method


@pytest.fixture(name="ticker_splits")
def _ticker_splits(mocker) -> Callable:
    def _method(splits: pd.Series | None = None) -> None:
        return mocker.patch(
            "yfinance.Ticker.splits",
            return_value=splits,
            new_callable=mocker.PropertyMock,
        )

    return _method


def test_yfinance_security_info_provider(ticker_info, ticker_splits):
    ticker_info(
        {"shortName": "Amazon", "currentPrice": "199.46", "currency": "USD"},
    )
    ticker_splits(AMZN_PSERIES)
    provider = YahooFinanceSecurityInfoProvider()
    security_info = provider.get_info(ISIN("AMZN-ISIN"))
    assert security_info.name == "Amazon"
    assert security_info.splits == AMZN_SPLITS
    assert provider.get_price(ISIN("AMZN-ISIN")) == Money("199.46", USD)


def test_yfinance_security_info_provider_security_not_found(ticker_info, ticker_splits):
    ticker_info(yfinance.exceptions.YFException)
    ticker_splits([])
    security_info_provider = YahooFinanceSecurityInfoProvider()
    with pytest.raises(DataProviderError):
        security_info_provider.get_info(ISIN("NOT-FOUND"))


def test_yfinance_security_info_provider_price_in_GBp(ticker_info):
    ticker_info(
        {"currentPrice": 1550, "currency": "GBp"},
    )
    provider = YahooFinanceSecurityInfoProvider()
    assert provider.get_price(ISIN("AMZN-ISIN")) == Money("15.50", GBP)


def test_yfinance_security_info_provider_exception_raised(ticker_info):
    ticker_info(yfinance.exceptions.YFException)
    provider = YahooFinanceSecurityInfoProvider()
    with pytest.raises(DataProviderError):
        provider.get_info(ISIN("AMZN-ISIN"))
    with pytest.raises(DataProviderError):
        provider.get_price(ISIN("AMZN-ISIN"))


def test_yfinance_security_info_provider_missing_field(ticker_info):
    ticker_info({})
    provider = YahooFinanceSecurityInfoProvider()
    with pytest.raises(DataProviderError):
        provider.get_info(ISIN("AMZN-ISIN"))


def test_yfinance_live_exchange_rate_provider(ticker_info):
    ticker_info({"bid": 0.75})
    provider = YahooFinanceLiveExchangeRateProvider()
    fx_rate = provider.get_rate(USD, GBP)
    assert fx_rate == Decimal("0.75")


def test_yfinance_live_exchange_rate_provider_exception_raised(ticker_info):
    ticker_info(yfinance.exceptions.YFException)
    provider = YahooFinanceLiveExchangeRateProvider()
    with pytest.raises(DataProviderError):
        provider.get_rate(USD, GBP)


def test_yfinance_live_exchange_rate_provider_missing_field(ticker_info):
    ticker_info({})
    provider = YahooFinanceLiveExchangeRateProvider()
    with pytest.raises(DataProviderError):
        provider.get_rate(USD, GBP)
