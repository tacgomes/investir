from collections.abc import Callable, Mapping
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

import pandas as pd
import pytest
import yfinance
from moneyed import GBP, USD, Money

from investir.config import config
from investir.findata import (
    CacheMissError,
    DataNotFoundError,
    RequestError,
    Split,
    YahooFinanceHistoricalExchangeRateProvider,
    YahooFinanceLiveExchangeRateProvider,
    YahooFinanceSecurityInfoProvider,
)
from investir.typing import ISIN


@pytest.fixture
def si_provider(tmp_path):
    return YahooFinanceSecurityInfoProvider(cache_file=tmp_path / "securities.yaml")


@pytest.fixture
def lr_provider(tmp_path):
    return YahooFinanceLiveExchangeRateProvider()


@pytest.fixture
def hr_provider(tmp_path):
    return YahooFinanceHistoricalExchangeRateProvider(
        cache_file=tmp_path / "rates.json"
    )


@pytest.fixture
def ticker_info(mocker) -> Callable:
    def _wrapper(info: Mapping[str, Any] | Exception) -> None:
        return mocker.patch(
            "yfinance.Ticker.info",
            return_value=info,
            new_callable=mocker.PropertyMock,
        )

    return _wrapper


@pytest.fixture(name="ticker_splits")
def _ticker_splits(mocker) -> Callable:
    def _wrapper(splits: pd.Series | None = None) -> None:
        return mocker.patch(
            "yfinance.Ticker.splits",
            return_value=splits,
            new_callable=mocker.PropertyMock,
        )

    return _wrapper


@pytest.fixture(name="history_mocker")
def _history_mocker(mocker) -> Callable:
    def _wrapper(response: pd.DataFrame | Exception | None = None) -> None:
        side_effect = response
        if isinstance(response, pd.DataFrame):
            side_effect = [response]  # type: ignore[assignment]

        mock = mocker.patch(
            "yfinance.Ticker.history",
            side_effect=side_effect,
        )

        return mock

    return _wrapper


def test_yfinance_security_info_provider_get_info(
    si_provider, ticker_info, ticker_splits
):
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

    security_info = si_provider.get_info(ISIN("AMZN-ISIN"))
    assert security_info.name == "Amazon"
    assert security_info.splits == splits1
    assert info_mock.call_count == 1

    # Cache should be used.
    si_provider.get_info(ISIN("AMZN-ISIN"))
    assert info_mock.call_count == 1

    # updated-after date is more recent than last-updated.
    ticker_splits(pd.concat([pd_series1, pd_series2]))
    security_info = si_provider.get_info(ISIN("AMZN-ISIN"), refresh_date=now)
    assert security_info.splits == splits1 + splits2
    assert info_mock.call_count == 2

    # Recreate provider. Cache should be loaded from file.
    si_provider = YahooFinanceSecurityInfoProvider(si_provider._cache_file)
    security_info = si_provider.get_info(
        ISIN("AMZN-ISIN"), refresh_date=now.replace(microsecond=0)
    )
    assert security_info.splits == splits1 + splits2
    assert info_mock.call_count == 2


def test_yfinance_security_info_provider_get_price(si_provider, ticker_info):
    info_mock = ticker_info({"currentPrice": "199.46", "currency": "USD"})

    assert si_provider.get_price(ISIN("AMZN-ISIN")) == Money("199.46", USD)
    assert info_mock.call_count == 2

    # Cache should be used.
    assert si_provider.get_price(ISIN("AMZN-ISIN")) == Money("199.46", USD)
    assert info_mock.call_count == 2


def test_yfinance_security_info_provider_price_in_GBp(si_provider, ticker_info):
    ticker_info({"currentPrice": 1550, "currency": "GBp"})
    assert si_provider.get_price(ISIN("AMZN-ISIN")) == Money("15.50", GBP)


def test_yfinance_security_info_provider_with_error(si_provider, ticker_info):
    ticker_info(yfinance.exceptions.YFException)
    with pytest.raises(RequestError):
        si_provider.get_info(ISIN("AMZN-ISIN"))
    with pytest.raises(RequestError):
        si_provider.get_price(ISIN("AMZN-ISIN"))

    config.offline = True
    with pytest.raises(CacheMissError):
        si_provider.get_info(ISIN("AMZN-ISIN"))
    with pytest.raises(CacheMissError):
        si_provider.get_price(ISIN("AMZN-ISIN"))


def test_yfinance_live_exchange_rate_provider(lr_provider, ticker_info):
    info_mock = ticker_info({"bid": 0.75})
    assert lr_provider.get_rate(USD, GBP) == Decimal("0.75")

    # Cache should be used.
    lr_provider.get_rate(USD, GBP)
    assert lr_provider.get_rate(GBP, USD) == Decimal("1.0") / Decimal("0.75")
    assert info_mock.call_count == 1


def test_yfinance_live_exchange_rate_provider_with_error(lr_provider, ticker_info):
    ticker_info(yfinance.exceptions.YFException)
    with pytest.raises(RequestError):
        lr_provider.get_rate(USD, GBP)

    config.offline = True
    with pytest.raises(CacheMissError):
        lr_provider.get_rate(USD, GBP)


def test_yfinance_historical_exchange_rate_provider(
    hr_provider,
    history_mocker,
):
    rates1 = pd.DataFrame(
        data={"Close": [1.24, 1.25, 1.26]},
        index=[datetime(2024, 1, 1), datetime(2024, 1, 2), datetime(2024, 1, 3)],
    )

    rates2 = pd.DataFrame(
        data={"Close": [1.27]},
        index=[datetime(2024, 1, 4)],
    )

    mock = history_mocker(rates1)

    # Test that historical rate is fetched online if not in cache.
    assert hr_provider.get_rate(GBP, USD, date(2024, 1, 1)) == Decimal(
        "1.24"
    )  # FIXME GBP-> USD
    assert mock.call_count == 1

    # Check all the historical rates were cached and we can read from
    # the cache.
    assert hr_provider.get_rate(GBP, USD, date(2024, 1, 1)) == Decimal("1.24")
    assert hr_provider.get_rate(GBP, USD, date(2024, 1, 2)) == Decimal("1.25")
    assert hr_provider.get_rate(GBP, USD, date(2024, 1, 3)) == Decimal("1.26")
    assert mock.call_count == 1

    # Check that we can the read inverse rate from the cache.
    assert hr_provider.get_rate(USD, GBP, date(2024, 1, 1)) == Decimal("1.0") / Decimal(
        "1.24"
    )
    assert mock.call_count == 1

    # Request new non-cached exchange rate.
    mock = history_mocker(rates2)
    assert hr_provider.get_rate(GBP, USD, date(2024, 1, 4)) == Decimal("1.27")
    assert mock.call_count == 1

    # Recreate provider. Cache should be loaded from file.
    hr_provider = YahooFinanceHistoricalExchangeRateProvider(hr_provider._cache_file)
    mock = history_mocker()
    assert hr_provider.get_rate(GBP, USD, date(2024, 1, 1)) == Decimal("1.24")
    assert hr_provider.get_rate(GBP, USD, date(2024, 1, 2)) == Decimal("1.25")
    assert hr_provider.get_rate(GBP, USD, date(2024, 1, 3)) == Decimal("1.26")
    assert hr_provider.get_rate(GBP, USD, date(2024, 1, 4)) == Decimal("1.27")
    assert mock.call_count == 0


def test_yfinance_historical_exchange_rate_provider_with_request_error(
    hr_provider, history_mocker
):
    history_mocker(yfinance.exceptions.YFException)
    with pytest.raises(RequestError):
        hr_provider.get_rate(GBP, USD, date(2024, 1, 1))


def test_yfinance_historical_exchange_rate_provider_with_data_not_found_error(
    hr_provider, history_mocker
):
    rates = pd.DataFrame(
        data={"Close": [1.24]},
        index=[datetime(2024, 1, 1)],
    )
    history_mocker(rates)
    with pytest.raises(DataNotFoundError):
        hr_provider.get_rate(GBP, USD, date(2024, 1, 2))


def test_yfinance_historical_exchange_rate_provider_with_cache_miss_error(
    hr_provider, history_mocker
):
    config.offline = True
    with pytest.raises(CacheMissError):
        hr_provider.get_rate(GBP, USD, date(2024, 1, 2))
