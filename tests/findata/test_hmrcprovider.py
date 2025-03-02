from collections.abc import Callable
from datetime import date
from decimal import Decimal
from io import BytesIO
from unittest.mock import MagicMock, Mock
from urllib.error import URLError

import pytest
from moneyed import EUR, GBP, USD

from investir.findata import DataProviderError, HmrcMonthlyExhangeRateProvider


@pytest.fixture(name="provider")
def _provider(tmp_path):
    return HmrcMonthlyExhangeRateProvider(cache_file=tmp_path / "rates.json")


@pytest.fixture(name="urlopen_mocker")
def _urlopen_mocker(mocker) -> Callable:
    def _method(response: str | Exception) -> None:
        side_effect = response
        if isinstance(response, str):
            header = bytes("Currency Code,Currency Units per £1\n", "utf-8")
            data = BytesIO(header + bytes(response, "utf-8"))

            charset_mock = Mock()
            charset_mock.get_content_charset.return_value = "utf-8"

            resp_mock = MagicMock()
            resp_mock.__enter__.return_value = resp_mock
            resp_mock.__iter__.return_value = data
            resp_mock.info.return_value = charset_mock

            side_effect = [resp_mock]  # type: ignore[assignment]

        mock = mocker.patch(
            "urllib.request.urlopen",
            side_effect=side_effect,
        )

        return mock

    return _method


def test_hmrc_historical_exchange_rate_provider(provider, urlopen_mocker):
    mock = urlopen_mocker("USD,1.24\nEUR,1.19")

    # Test that historical rate is fetched online if not in cache.
    assert provider.get_rate(GBP, USD, date(2024, 1, 1)) == Decimal("1.24")
    assert mock.call_count == 1

    # Check all the historical rates were cached and we can read from
    # the cache.
    assert provider.get_rate(GBP, USD, date(2024, 1, 2)) == Decimal("1.24")
    assert provider.get_rate(GBP, USD, date(2024, 1, 31)) == Decimal("1.24")
    assert provider.get_rate(GBP, EUR, date(2024, 1, 1)) == Decimal("1.19")
    assert mock.call_count == 1

    # Check that we can the read inverse rate from the cache.
    assert provider.get_rate(USD, GBP, date(2024, 1, 1)) == Decimal("1.0") / Decimal(
        "1.24"
    )
    assert mock.call_count == 1

    # Request new non-cached exchange rate.
    mock = urlopen_mocker("USD,1.27")
    assert provider.get_rate(GBP, USD, date(2024, 2, 1)) == Decimal("1.27")
    assert mock.call_count == 1

    # Recreate provider. Cache should be loaded from file.
    provider = HmrcMonthlyExhangeRateProvider(provider._cache_file)
    mock = urlopen_mocker("")
    assert provider.get_rate(GBP, USD, date(2024, 1, 1)) == Decimal("1.24")
    assert provider.get_rate(GBP, USD, date(2024, 1, 31)) == Decimal("1.24")
    assert provider.get_rate(GBP, EUR, date(2024, 1, 2)) == Decimal("1.19")
    assert provider.get_rate(GBP, USD, date(2024, 2, 3)) == Decimal("1.27")
    assert mock.call_count == 0


def test_hmrc_historical_exchange_rate_provider_exception_raised(
    provider, urlopen_mocker
):
    urlopen_mocker(URLError("Some error"))
    with pytest.raises(DataProviderError):
        provider.get_rate(GBP, USD, date(2024, 1, 1))


def test_hmrc_historical_exchange_rate_provider_rate_not_found(
    provider, urlopen_mocker
):
    urlopen_mocker("USD,1.24")
    with pytest.raises(DataProviderError):
        provider.get_rate(GBP, EUR, date(2024, 1, 1))
