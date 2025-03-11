from collections.abc import Callable
from datetime import date
from decimal import Decimal

import pytest
from moneyed import EUR, GBP, USD

from investir.findata import (
    DataNotFoundError,
    LocalHistoricalExchangeRateProvider,
    ProviderError,
)

TEST_DATA = """
Date,Currency,Rate
2024-01-01,USD,1.24
2024-01-02,EUR,1.19
"""


@pytest.fixture
def make_provider(tmp_path) -> Callable:
    def _wrapper(csv_content: str):
        rates_file = tmp_path / "rates.csv"
        rates_file.write_text(csv_content)
        return LocalHistoricalExchangeRateProvider(rates_file=rates_file)

    return _wrapper


def test_local_historical_exchange_rate_provider(make_provider):
    provider = make_provider(TEST_DATA.strip())
    assert provider.get_rate(GBP, USD, date(2024, 1, 1)) == Decimal("1.24")
    assert provider.get_rate(GBP, EUR, date(2024, 1, 2)) == Decimal("1.19")
    assert provider.get_rate(USD, GBP, date(2024, 1, 1)) == Decimal("1.0") / Decimal(
        "1.24"
    )


def test_local_historical_exchange_rate_provider_with_invalid_file(
    make_provider,
):
    with pytest.raises(ProviderError):
        make_provider("")

    with pytest.raises(ProviderError):
        make_provider("Date,Currency")

    with pytest.raises(ProviderError):
        make_provider("Date,Currency,Rate,Unknown")


def test_local_historical_exchange_rate_provider_with_data_not_found_error(
    make_provider,
):
    provider = make_provider(TEST_DATA.strip())
    with pytest.raises(DataNotFoundError):
        provider.get_rate(GBP, EUR, date(2024, 1, 3))


def test_local_historical_exchange_rate_provider_with_invalid_arguments(
    make_provider,
):
    provider = make_provider(TEST_DATA.strip())
    with pytest.raises(ValueError):
        provider.get_rate(USD, EUR, date(2024, 1, 1))
