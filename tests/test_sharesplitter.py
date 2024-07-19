from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import PropertyMock, Mock

import pandas as pd
import pytest
import yaml

from investir.sharesplitter import ShareSplitter, Split, VERSION
from investir.transaction import Acquisition, Disposal
from investir.trhistory import TrHistory
from investir.typing import Ticker


ORDER1 = Acquisition(
    datetime(2018, 1, 1, tzinfo=timezone.utc),
    ticker=Ticker("AMZN"),
    amount=Decimal("10.0"),
    quantity=Decimal("1.0"),
)

ORDER2 = Acquisition(
    datetime(2020, 1, 1, tzinfo=timezone.utc),
    ticker=Ticker("AMZN"),
    amount=Decimal("10.0"),
    quantity=Decimal("1.0"),
)

ORDER3 = Disposal(
    datetime(2022, 1, 1, tzinfo=timezone.utc),
    ticker=Ticker("AMZN"),
    amount=Decimal("25.0"),
    quantity=Decimal("2.0"),
)

ORDER4 = Acquisition(
    datetime(2024, 1, 1, tzinfo=timezone.utc),
    ticker=Ticker("GOOG"),
    amount=Decimal("15.0"),
    quantity=Decimal("2.0"),
)

ORDER5 = Acquisition(
    datetime(2024, 6, 1, tzinfo=timezone.utc),
    ticker=Ticker("AAPL"),
    amount=Decimal("15.0"),
    quantity=Decimal("2.0"),
)

AMZN_PSERIES = pd.Series(
    data=[10.0, 3.0],
    index=[
        pd.Timestamp(2019, 1, 1, tzinfo=timezone.utc),
        pd.Timestamp(2021, 1, 1, tzinfo=timezone.utc),
    ],
)

GOOG_PSERIES = pd.Series()

AMZN_SPLITS = [
    Split(
        date_effective=datetime(2019, 1, 1, tzinfo=timezone.utc), ratio=Decimal("10.0")
    ),
    Split(
        date_effective=datetime(2021, 1, 1, tzinfo=timezone.utc), ratio=Decimal("3.0")
    ),
]

GOOG_SPLITS: list[Split] = []


@pytest.fixture(name="ticker_mocker")
def _ticker_mocker(mocker):
    def _method(series):
        ticker_mock = Mock()
        splits_prop_mock = PropertyMock(side_effect=series)
        type(ticker_mock).splits = splits_prop_mock
        mocker.patch("yfinance.Ticker", return_value=ticker_mock)
        return splits_prop_mock

    return _method


def test_sharesplitter_initialisation_without_cache(ticker_mocker, tmp_path):
    cache_file = tmp_path / "cache.yaml"

    splits_prop_mock = ticker_mocker([AMZN_PSERIES, GOOG_PSERIES])

    tr_hist = TrHistory()
    tr_hist.insert_orders([ORDER1, ORDER2, ORDER3, ORDER4])

    share_splitter = ShareSplitter(tr_hist, cache_file)
    assert share_splitter.splits("AMZN") == AMZN_SPLITS
    assert share_splitter.splits("GOOG") == GOOG_SPLITS
    assert splits_prop_mock.call_count == 2

    assert cache_file.exists()
    with cache_file.open("r") as file:
        data = yaml.load(file, Loader=yaml.FullLoader)
    assert data["version"] == VERSION
    assert data["tickers"].get("AMZN").splits == AMZN_SPLITS
    assert data["tickers"].get("GOOG").splits == GOOG_SPLITS

    share_splitter = ShareSplitter(tr_hist, cache_file)
    assert share_splitter.splits("AMZN") == AMZN_SPLITS
    assert share_splitter.splits("GOOG") == GOOG_SPLITS
    assert splits_prop_mock.call_count == 2


def test_sharesplitter_cache_is_updated(ticker_mocker, tmp_path):
    cache_file = tmp_path / "cache.yaml"
    cache_file.write_text(
        """
    tickers:
        AMZN: !ticker
            last_updated: 2022-01-01 00:00:00+00:00
            splits:
            - !split '2019-01-01 00:00:00+00:00, 10'
            - !split '2021-01-01 00:00:00+00:00, 3'
            yaml_tag: '!ticker'
        GOOG: !ticker
            last_updated: 2024-01-01 00:00:00+00:00
            splits:
            - !split '2021-05-12 00:00:00+00:00, 20'
            yaml_tag: '!ticker'
        """
    )

    aapl_pseries = pd.Series()

    amzn_pseries = pd.concat(
        [AMZN_PSERIES, pd.Series(data=[40.0], index=[pd.Timestamp(2024, 1, 1)])]
    )
    amazn_splits = AMZN_SPLITS + [
        Split(date_effective=datetime(2024, 1, 1), ratio=Decimal("40.0"))
    ]

    splits_prop_mock = ticker_mocker([aapl_pseries, amzn_pseries, GOOG_PSERIES])

    tr_hist = TrHistory()
    tr_hist.insert_orders([ORDER1, ORDER2, ORDER3, ORDER4, ORDER5])

    share_splitter = ShareSplitter(tr_hist, cache_file)
    assert not share_splitter.splits("AAPL")
    assert share_splitter.splits("AMZN") == amazn_splits
    assert share_splitter.splits("GOOG") == GOOG_SPLITS
    assert splits_prop_mock.call_count == 3

    with cache_file.open("r") as file:
        data = yaml.load(file, yaml.FullLoader)

    assert tuple(data["tickers"].keys()) == ("AAPL", "AMZN", "GOOG")
    assert not data["tickers"].get("AAPL").splits
    assert data["tickers"].get("AMZN").splits == amazn_splits
    assert data["tickers"].get("GOOG").splits == GOOG_SPLITS
