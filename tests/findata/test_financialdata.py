import os
from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, NamedTuple
from unittest.mock import Mock

import pytest
import yaml
from moneyed import GBP, USD, Money

from investir.findata import (
    DataProviderError,
    FinancialData,
    SecurityInfo,
    Split,
    YahooFinanceExchangeRateProvider,
    YahooFinanceSecurityInfoProvider,
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
    datetime(2024, 3, 1, tzinfo=timezone.utc),
    isin=ISIN("NOTF-ISIN"),
    name="Not Found",
    amount=Decimal("5.0"),
    quantity=Decimal("1.0"),
)

ORDER6 = Acquisition(
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


class DataProviderMocks(NamedTuple):
    fech_info: Mock
    fetch_price: Mock
    fetch_exchange_rate: Mock


@pytest.fixture(name="make_financial_data")
def _make_financial_data(mocker) -> Callable:
    def _method(
        tr_hist: TrHistory | None = None,
        cache_file: Path = Path(os.devnull),
        security_info: Sequence[SecurityInfo | Exception] | None = None,
        price: Money | Exception | None = None,
        fx_rate: Decimal | Exception | None = None,
    ) -> tuple[FinancialData, Any]:
        security_info_provider = YahooFinanceSecurityInfoProvider()
        exchange_rate_provider = YahooFinanceExchangeRateProvider()

        mocks = DataProviderMocks(
            mocker.patch.object(
                security_info_provider, "fech_info", side_effect=security_info
            ),
            mocker.patch.object(
                security_info_provider, "fetch_price", side_effect=[price]
            ),
            mocker.patch.object(
                exchange_rate_provider, "fetch_exchange_rate", side_effect=[fx_rate]
            ),
        )

        if tr_hist is None:
            tr_hist = TrHistory()

        findata = FinancialData(
            security_info_provider, exchange_rate_provider, tr_hist, cache_file
        )

        return findata, mocks

    return _method


def test_initialisation_without_pre_existing_cache(make_financial_data, tmp_path):
    cache_file = tmp_path / "cache.yaml"

    tr_hist = TrHistory(orders=[ORDER1, ORDER2, ORDER3, ORDER4, ORDER5])

    findata, mocks = make_financial_data(
        tr_hist,
        cache_file,
        [
            SecurityInfo(name="Amazon", splits=AMZN_SPLITS),
            SecurityInfo(name="Netflix", splits=NFLX_SPLITS),
            DataProviderError,
        ],
    )

    assert findata.get_security_info(ISIN("AMZN-ISIN")).name == "Amazon"
    assert findata.get_security_info(ISIN("AMZN-ISIN")).splits == AMZN_SPLITS
    assert findata.get_security_info(ISIN("NFLX-ISIN")).name == "Netflix"
    assert findata.get_security_info(ISIN("NFLX-ISIN")).splits == NFLX_SPLITS
    assert findata.get_security_info(ISIN("NOTF-ISIN")).name == "Not Found"
    assert findata.get_security_info(ISIN("NOTF-ISIN")).splits == []
    assert mocks.fech_info.call_count == 3

    assert cache_file.exists()
    with cache_file.open("r") as file:
        data = yaml.load(file, Loader=yaml.FullLoader)
    assert data["version"] == FinancialData.VERSION
    assert data["securities"].get(ISIN("AMZN-ISIN")).name == "Amazon"
    assert data["securities"].get(ISIN("AMZN-ISIN")).splits == AMZN_SPLITS
    assert data["securities"].get(ISIN("NFLX-ISIN")).name == "Netflix"
    assert data["securities"].get(ISIN("NFLX-ISIN")).splits == NFLX_SPLITS
    assert data["securities"].get(ISIN("NOTF-ISIN")).name == "Not Found"
    assert data["securities"].get(ISIN("NOTF-ISIN")).splits == []

    findata, mocks = make_financial_data(tr_hist, cache_file, None)
    assert findata.get_security_info(ISIN("AMZN-ISIN")).name == "Amazon"
    assert findata.get_security_info(ISIN("AMZN-ISIN")).splits == AMZN_SPLITS
    assert findata.get_security_info(ISIN("NFLX-ISIN")).name == "Netflix"
    assert findata.get_security_info(ISIN("NFLX-ISIN")).splits == NFLX_SPLITS
    assert findata.get_security_info(ISIN("NOTF-ISIN")).name == "Not Found"
    assert findata.get_security_info(ISIN("NOTF-ISIN")).splits == []
    assert mocks.fech_info.call_count == 0


def test_cache_is_updated(make_financial_data, tmp_path):
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

    amazn_splits = [
        *AMZN_SPLITS,
        Split(date_effective=datetime(2024, 1, 1), ratio=Decimal("40.0")),
    ]

    tr_hist = TrHistory(orders=[ORDER1, ORDER2, ORDER3, ORDER4, ORDER5, ORDER6])

    findata, mocks = make_financial_data(
        tr_hist,
        cache_file,
        [
            SecurityInfo(name="Amazon", splits=amazn_splits),
            SecurityInfo(name="Microsoft", splits=[]),
            SecurityInfo(name="Netflix", splits=NFLX_SPLITS),
            DataProviderError,
        ],
    )

    assert findata.get_security_info(ISIN("AMZN-ISIN")).splits == amazn_splits
    assert findata.get_security_info(ISIN("NFLX-ISIN")).splits == NFLX_SPLITS
    assert not findata.get_security_info(ISIN("MSFT-ISIN")).splits
    assert mocks.fech_info.call_count == 4

    with cache_file.open("r") as file:
        data = yaml.load(file, yaml.FullLoader)

    assert tuple(data["securities"].keys()) == (
        ISIN("AMZN-ISIN"),
        ISIN("MSFT-ISIN"),
        ISIN("NFLX-ISIN"),
        ISIN("NOTF-ISIN"),
    )

    assert data["securities"].get(ISIN("AMZN-ISIN")).name == "Amazon"
    assert data["securities"].get(ISIN("AMZN-ISIN")).splits == amazn_splits
    assert data["securities"].get(ISIN("MSFT-ISIN")).name == "Microsoft"
    assert data["securities"].get(ISIN("MSFT-ISIN")).splits == []
    assert data["securities"].get(ISIN("NFLX-ISIN")).name == "Netflix"
    assert data["securities"].get(ISIN("NFLX-ISIN")).splits == NFLX_SPLITS
    assert data["securities"].get(ISIN("NOTF-ISIN")).name == "Not Found"
    assert data["securities"].get(ISIN("NOTF-ISIN")).splits == []


def test_empty_cache_does_not_raise_exception(make_financial_data):
    make_financial_data()


def test_get_security_price(make_financial_data):
    findata, mocks = make_financial_data(price=Money("199.46", USD))
    for _ in range(2):
        assert findata.get_security_price(ISIN("AMZN-ISIN")) == Money("199.46", USD)
    assert mocks.fetch_price.call_count == 1


def test_get_security_price_exception_raised(make_financial_data):
    findata, _ = make_financial_data(price=DataProviderError)
    assert findata.get_security_price(ISIN("AMZN-ISIN")) is None


def test_get_foreign_exchange_rate(make_financial_data):
    findata, mocks = make_financial_data(fx_rate=Decimal("1.3042"))
    for _ in range(2):
        assert findata.get_foreign_exchange_rate(GBP, USD) == Decimal("1.3042")
        assert findata.get_foreign_exchange_rate(USD, GBP) == Decimal("1.0") / Decimal(
            "1.3042"
        )
    assert mocks.fetch_exchange_rate.call_count == 1


def test_get_foreign_exchange_rate_exception_raised(make_financial_data):
    findata, _ = make_financial_data(fx_rate=DataProviderError)
    assert findata.get_foreign_exchange_rate(GBP, USD) is None


def test_convert_currency(make_financial_data):
    findata, mocks = make_financial_data(fx_rate=Decimal("1.3042"))
    assert findata.convert_currency(Decimal("10.0"), GBP, USD) == Decimal("13.042")
    assert mocks.fetch_exchange_rate.call_count == 1


def test_convert_currency_same_currencies(make_financial_data):
    findata, mocks = make_financial_data(fx_rate=Decimal("1.3042"))
    assert findata.convert_currency(Decimal("10.0"), GBP, GBP) == Decimal("10.0")
    assert mocks.fetch_exchange_rate.call_count == 0


def test_api_without_data_providers_set():
    findata = FinancialData(None, None, TrHistory(), Path(os.devnull))
    assert findata.get_security_price(ISIN("AMZN-ISIN")) is None
    assert findata.get_foreign_exchange_rate(GBP, USD) is None
    assert findata.convert_currency(Decimal("10.0"), GBP, USD) is None
