from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import yaml

from investir.securitiesdatacache import VERSION, SecuritiesDataCache
from investir.securitiesdataprovider import (
    SecurityData,
    Split,
    YahooFinanceDataProvider,
)
from investir.transaction import Acquisition, Disposal
from investir.trhistory import TrHistory
from investir.typing import ISIN

ORDER1 = Acquisition(
    datetime(2018, 1, 1, tzinfo=timezone.utc),
    isin=ISIN("AMZN-ISIN"),
    name="Amazon",
    amount=Decimal("10.0"),
    quantity=Decimal("1.0"),
)

ORDER2 = Acquisition(
    datetime(2020, 1, 1, tzinfo=timezone.utc),
    isin=ISIN("AMZN-ISIN"),
    name="Amazon",
    amount=Decimal("10.0"),
    quantity=Decimal("1.0"),
)

ORDER3 = Disposal(
    datetime(2022, 1, 1, tzinfo=timezone.utc),
    isin=ISIN("AMZN-ISIN"),
    name="Amazon",
    amount=Decimal("25.0"),
    quantity=Decimal("2.0"),
)

ORDER4 = Acquisition(
    datetime(2024, 1, 1, tzinfo=timezone.utc),
    isin=ISIN("NFLX-ISIN"),
    name="Netflix",
    amount=Decimal("15.0"),
    quantity=Decimal("2.0"),
)

ORDER5 = Acquisition(
    datetime(2024, 6, 1, tzinfo=timezone.utc),
    isin=ISIN("MSFT-ISIN"),
    name="Microsoft",
    amount=Decimal("15.0"),
    quantity=Decimal("2.0"),
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


@pytest.fixture(name="create_securities_data_cache")
def _create_securities_data_cache(mocker) -> Callable:
    def _method(
        tr_hist: TrHistory, cache_file: Path, data: Sequence[SecurityData]
    ) -> tuple[SecuritiesDataCache, Any]:
        data_provider = YahooFinanceDataProvider()
        mock = mocker.patch.object(data_provider, "get_security_data")
        mock.side_effect = data
        return SecuritiesDataCache(data_provider, tr_hist, cache_file), mock

    return _method


def test_securities_data_initialisation_without_cache(
    create_securities_data_cache, tmp_path
):
    cache_file = tmp_path / "cache.yaml"

    tr_hist = TrHistory(orders=[ORDER1, ORDER2, ORDER3, ORDER4])

    data_cache, data_provider_mock = create_securities_data_cache(
        tr_hist,
        cache_file,
        [
            SecurityData(name="Amazon", splits=AMZN_SPLITS),
            SecurityData(name="Netflix", splits=NFLX_SPLITS),
        ],
    )
    assert data_cache[ISIN("AMZN-ISIN")].name == "Amazon"
    assert data_cache[ISIN("AMZN-ISIN")].splits == AMZN_SPLITS
    assert data_cache[ISIN("NFLX-ISIN")].name == "Netflix"
    assert data_cache[ISIN("NFLX-ISIN")].splits == NFLX_SPLITS
    assert data_provider_mock.call_count == 2

    assert cache_file.exists()
    with cache_file.open("r") as file:
        data = yaml.load(file, Loader=yaml.FullLoader)
    assert data["version"] == VERSION
    assert data["securities"].get(ISIN("AMZN-ISIN")).name == "Amazon"
    assert (
        data["securities"].get(ISIN("AMZN-ISIN")).splits
        == data["securities"].get(ISIN("AMZN-ISIN")).splits
    )
    assert data["securities"].get(ISIN("NFLX-ISIN")).name == "Netflix"
    assert data["securities"].get(ISIN("NFLX-ISIN")).splits == NFLX_SPLITS

    data_cache, data_provider_mock = create_securities_data_cache(
        tr_hist, cache_file, None
    )
    assert data_cache[ISIN("AMZN-ISIN")].name == "Amazon"
    assert data_cache[ISIN("AMZN-ISIN")].splits == AMZN_SPLITS
    assert data_cache[ISIN("NFLX-ISIN")].name == "Netflix"
    assert data_cache[ISIN("NFLX-ISIN")].splits == NFLX_SPLITS
    assert data_provider_mock.call_count == 0


def test_securities_data_cache_is_updated(create_securities_data_cache, tmp_path):
    cache_file = tmp_path / "cache.yaml"
    cache_file.write_text(
        """
    securities:
        AMZN-ISIN: !security
            name: Amazon
            splits:
            - !split '2019-01-01 00:00:00+00:00, 10'
            - !split '2021-01-01 00:00:00+00:00, 3'
            last_updated: 2022-01-01 00:00:00+00:00
        NFLX-ISIN: !security
            name: Netflix
            splits:
            - !split '2021-05-12 00:00:00+00:00, 20'
            last_updated: 2024-01-01 00:00:00+00:00
        """
    )

    amazn_splits = AMZN_SPLITS + [
        Split(date_effective=datetime(2024, 1, 1), ratio=Decimal("40.0"))
    ]

    tr_hist = TrHistory(orders=[ORDER1, ORDER2, ORDER3, ORDER4, ORDER5])

    data_cache, data_provider_mock = create_securities_data_cache(
        tr_hist,
        cache_file,
        [
            SecurityData(name="Amazon", splits=amazn_splits),
            SecurityData(name="Microsoft", splits=[]),
            SecurityData(name="Netflix", splits=NFLX_SPLITS),
        ],
    )

    assert data_cache[ISIN("AMZN-ISIN")].splits == amazn_splits
    assert data_cache[ISIN("NFLX-ISIN")].splits == NFLX_SPLITS
    assert not data_cache[ISIN("MSFT-ISIN")].splits
    assert data_provider_mock.call_count == 3

    with cache_file.open("r") as file:
        data = yaml.load(file, yaml.FullLoader)

    assert tuple(data["securities"].keys()) == (
        ISIN("AMZN-ISIN"),
        ISIN("MSFT-ISIN"),
        ISIN("NFLX-ISIN"),
    )

    assert data["securities"].get(ISIN("AMZN-ISIN")).name == "Amazon"
    assert data["securities"].get(ISIN("AMZN-ISIN")).splits == amazn_splits
    assert data["securities"].get(ISIN("NFLX-ISIN")).name == "Netflix"
    assert data["securities"].get(ISIN("NFLX-ISIN")).splits == NFLX_SPLITS
    assert data["securities"].get(ISIN("MSFT-ISIN")).name == "Microsoft"
    assert not data["securities"].get(ISIN("MSFT-ISIN")).splits
