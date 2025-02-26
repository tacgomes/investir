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


def test_yfinance_security_info_provider_get_info(ticker_info, ticker_splits, tmp_path):
    cache_file = tmp_path / "cache.yaml"
    now = datetime.now(timezone.utc)

    pd_series1 = pd.Series(
        data=[10.0, 3.0],
        index=[
            pd.Timestamp(2019, 1, 1, tzinfo=timezone.utc),
            pd.Timestamp(2021, 1, 1, tzinfo=timezone.utc),
        ],
    )
    pd_series2 = pd.Series(
        data=[2.0],
        index=[
            pd.Timestamp(2024, 1, 1, tzinfo=timezone.utc),
        ],
    )
    splits1 = [
        Split(
            date_effective=datetime(2019, 1, 1, tzinfo=timezone.utc),
            ratio=Decimal("10"),
        ),
        Split(
            date_effective=datetime(2021, 1, 1, tzinfo=timezone.utc),
            ratio=Decimal("3"),
        ),
    ]
    splits2 = [
        Split(
            date_effective=datetime(2024, 1, 1, tzinfo=timezone.utc),
            ratio=Decimal("2"),
        ),
    ]

    info_mock = ticker_info({"shortName": "Amazon"})
    ticker_splits(pd_series1)
    provider = YahooFinanceSecurityInfoProvider(cache_file)

    security_info = provider.get_info(ISIN("AMZN-ISIN"))
    assert security_info.name == "Amazon"
    assert security_info.splits == splits1
    assert info_mock.call_count == 1

    # Cache should be used.
    provider.get_info(ISIN("AMZN-ISIN"))
    assert info_mock.call_count == 1

    # updated-after date is more recent than last-updated.
    ticker_splits(pd.concat([pd_series1, pd_series2]))
    security_info = provider.get_info(ISIN("AMZN-ISIN"), refresh_date=now)
    assert security_info.splits == splits1 + splits2
    assert info_mock.call_count == 2

    # Recreate provider. Cache should be loaded from file.
    provider = YahooFinanceSecurityInfoProvider(cache_file)
    security_info = provider.get_info(
        ISIN("AMZN-ISIN"), refresh_date=now.replace(microsecond=0)
    )
    assert security_info.splits == splits1 + splits2
    assert info_mock.call_count == 2


def test_yfinance_security_info_provider_get_price(ticker_info):
    info_mock = ticker_info({"currentPrice": "199.46", "currency": "USD"})
    provider = YahooFinanceSecurityInfoProvider()

    assert provider.get_price(ISIN("AMZN-ISIN")) == Money("199.46", USD)
    assert info_mock.call_count == 2

    # Cache should be used.
    assert provider.get_price(ISIN("AMZN-ISIN")) == Money("199.46", USD)
    assert info_mock.call_count == 2


def test_yfinance_security_info_provider_price_in_GBp(ticker_info):
    ticker_info({"currentPrice": 1550, "currency": "GBp"})
    provider = YahooFinanceSecurityInfoProvider()
    assert provider.get_price(ISIN("AMZN-ISIN")) == Money("15.50", GBP)


def test_yfinance_security_info_provider_exception_raised(ticker_info):
    ticker_info(yfinance.exceptions.YFException)
    provider = YahooFinanceSecurityInfoProvider()
    with pytest.raises(DataProviderError):
        provider.get_info(ISIN("AMZN-ISIN"))
    with pytest.raises(DataProviderError):
        provider.get_price(ISIN("AMZN-ISIN"))


def test_yfinance_live_exchange_rate_provider(ticker_info):
    info_mock = ticker_info({"bid": 0.75})
    provider = YahooFinanceLiveExchangeRateProvider()
    assert provider.get_rate(USD, GBP) == Decimal("0.75")

    # Cache should be used.
    provider.get_rate(USD, GBP)
    assert provider.get_rate(GBP, USD) == Decimal("1.0") / Decimal("0.75")
    assert info_mock.call_count == 1


def test_yfinance_live_exchange_rate_provider_exception_raised(ticker_info):
    ticker_info(yfinance.exceptions.YFException)
    provider = YahooFinanceLiveExchangeRateProvider()
    with pytest.raises(DataProviderError):
        provider.get_rate(USD, GBP)
