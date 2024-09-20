from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import Mock, PropertyMock

import pandas as pd
import pytest
import yfinance

from investir.securitiesdataprovider import YahooFinanceDataProvider
from investir.securitydata import Split
from investir.typing import ISIN

AMZN_PSERIES = pd.Series(
    data=[10.0, 3.0],
    index=[
        pd.Timestamp(2019, 1, 1, tzinfo=timezone.utc),
        pd.Timestamp(2021, 1, 1, tzinfo=timezone.utc),
    ],
)

NFLX_PSERIES = pd.Series(
    data=[5.0],
    index=[
        pd.Timestamp(2023, 1, 1, tzinfo=timezone.utc),
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

NFLX_SPLITS = [
    Split(
        date_effective=datetime(2023, 1, 1, tzinfo=timezone.utc), ratio=Decimal("5.0")
    ),
]


@pytest.fixture(name="yf_ticker_mocker")
def _yf_ticker_mocker(mocker) -> Callable:
    def _method(
        info_se: Sequence[str] | Exception, splits_se: Sequence[pd.Series]
    ) -> tuple[PropertyMock, PropertyMock]:
        ticker_mock = Mock()

        splits_prop_mock = PropertyMock(side_effect=splits_se)
        type(ticker_mock).splits = splits_prop_mock

        info_prop_mock = PropertyMock(side_effect=info_se)
        type(ticker_mock).info = info_prop_mock

        mocker.patch("yfinance.Ticker", return_value=ticker_mock)
        return info_prop_mock, splits_prop_mock

    return _method


def test_dataprovider_security_data(yf_ticker_mocker):
    info_prop_mock, splits_prop_mock = yf_ticker_mocker(
        [{"shortName": "Amazon"}, {"shortName": "Netflix"}],
        [AMZN_PSERIES, NFLX_PSERIES],
    )
    data_provider = YahooFinanceDataProvider()
    security_data = data_provider.get_security_data(ISIN("AMZN-ISIN"))
    assert security_data.name == "Amazon"
    assert security_data.splits == AMZN_SPLITS
    security_data = data_provider.get_security_data(ISIN("NFLX-ISIN"))
    assert security_data.name == "Netflix"
    assert security_data.splits == NFLX_SPLITS
    assert info_prop_mock.call_count == 2
    assert splits_prop_mock.call_count == 2


def test_dataprovider_security_not_found(yf_ticker_mocker):
    yf_ticker_mocker(yfinance.exceptions.YFException, [])
    data_provider = YahooFinanceDataProvider()
    security_data = data_provider.get_security_data(ISIN("NOT-FOUND"))
    assert security_data is not None
