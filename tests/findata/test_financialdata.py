from collections.abc import Callable
from datetime import date, datetime
from decimal import Decimal
from typing import Any, NamedTuple
from unittest.mock import Mock

import pytest
from moneyed import GBP, USD, Money

from investir.findata import (
    DataProviderError,
    FinancialData,
    SecurityInfo,
    Split,
    YahooFinanceHistoricalExchangeRateProvider,
    YahooFinanceLiveExchangeRateProvider,
    YahooFinanceSecurityInfoProvider,
)
from investir.typing import ISIN


class DataProviderMocks(NamedTuple):
    get_info: Mock
    get_price: Mock
    get_rate_live: Mock
    get_rate_historical: Mock


@pytest.fixture(name="make_financial_data")
def _make_financial_data(mocker) -> Callable:
    def _method(
        security_info: SecurityInfo | Exception | None = None,
        price: Money | Exception | None = None,
        live_rate: Decimal | Exception | None = None,
        historical_rate: Decimal | Exception | None = None,
    ) -> tuple[FinancialData, Any]:
        security_info_provider = YahooFinanceSecurityInfoProvider()
        live_rates_provider = YahooFinanceLiveExchangeRateProvider()
        historical_rates_provider = YahooFinanceHistoricalExchangeRateProvider()

        mocks = DataProviderMocks(
            mocker.patch.object(
                security_info_provider, "get_info", side_effect=[security_info]
            ),
            mocker.patch.object(
                security_info_provider, "get_price", side_effect=[price]
            ),
            mocker.patch.object(
                live_rates_provider, "get_rate", side_effect=[live_rate]
            ),
            mocker.patch.object(
                historical_rates_provider, "get_rate", side_effect=[historical_rate]
            ),
        )

        findata = FinancialData(
            security_info_provider, live_rates_provider, historical_rates_provider
        )

        return findata, mocks

    return _method


def test_get_security_info(make_financial_data):
    security_info = SecurityInfo(
        "Amazon", [Split(datetime(2024, 1, 1), Decimal("2.3"))]
    )
    findata, _ = make_financial_data(security_info=security_info)
    assert findata.get_security_info(ISIN("AMZN-ISIN")) == security_info


def test_get_security_info_exception_raised(make_financial_data):
    findata, _ = make_financial_data(security_info=DataProviderError)
    assert findata.get_security_info(ISIN("AMZN-ISIN")) == SecurityInfo()


def test_get_security_price(make_financial_data):
    findata, _ = make_financial_data(price=Money("199.46", USD))
    assert findata.get_security_price(ISIN("AMZN-ISIN")) == Money("199.46", USD)


def test_get_security_price_exception_raised(make_financial_data):
    findata, _ = make_financial_data(price=DataProviderError)
    assert findata.get_security_price(ISIN("AMZN-ISIN")) is None


def test_get_exchange_rate_live(make_financial_data):
    findata, _ = make_financial_data(live_rate=Decimal("1.3042"))
    assert findata.get_exchange_rate(GBP, USD) == Decimal("1.3042")


def test_get_exchange_rate_historical(make_financial_data):
    findata, _ = make_financial_data(historical_rate=Decimal("1.3042"))
    assert findata.get_exchange_rate(GBP, USD, date(2024, 1, 1)) == Decimal("1.3042")


def test_get_exchange_rate_exception_raised(make_financial_data):
    findata, _ = make_financial_data(live_rate=DataProviderError)
    assert findata.get_exchange_rate(GBP, USD) is None
    findata, _ = make_financial_data(historical_rate=DataProviderError)
    assert findata.get_exchange_rate(GBP, USD, date(2024, 1, 1)) is None


def test_convert_money_live(make_financial_data):
    findata, _ = make_financial_data(live_rate=Decimal("1.3042"))
    assert findata.convert_money(Money("10.0", GBP), USD) == Money("13.042", USD)


def test_convert_money_historical(make_financial_data):
    findata, _ = make_financial_data(historical_rate=Decimal("1.3042"))
    assert findata.convert_money(Money("10.0", GBP), USD, date(2024, 1, 1)) == Money(
        "13.042", USD
    )


def test_convert_money_to_same_currency(make_financial_data):
    findata, mocks = make_financial_data(live_rate=Decimal("1.3042"))
    assert findata.convert_money(Money("10.0", GBP), GBP) == Money("10.0", GBP)
    assert mocks.get_rate_live.call_count == 0


def test_api_without_data_providers_set():
    findata = FinancialData(None, None, None)
    assert findata.get_security_price(ISIN("AMZN-ISIN")) is None
    assert findata.get_exchange_rate(GBP, USD) is None
    assert findata.convert_money(Money("10.0", GBP), USD) is None
