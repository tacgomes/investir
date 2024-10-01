import logging
from pathlib import Path

import yaml

from .securitiesdataprovider import SecuritiesDataProvider
from .securitydata import SecurityData
from .trhistory import TrHistory
from .typing import ISIN

logger = logging.getLogger(__name__)

VERSION = 1


class SecuritiesDataCache:  # pylint: disable=too-few-public-methods
    def __init__(
        self,
        data_provider: SecuritiesDataProvider,
        tr_hist: TrHistory,
        cache_file: Path,
    ) -> None:
        self._data_provider = data_provider
        self._tr_hist = tr_hist
        self._cache_file = cache_file
        self._securities_data: dict[ISIN, SecurityData] = {}

        self._initialise()

    def _initialise(self) -> None:
        self._load_cache()

        orders = self._tr_hist.orders
        update_cache = False

        for isin, name in self._tr_hist.securities:
            if (security_data := self._securities_data.get(isin)) is not None:
                last_order = next(o for o in reversed(orders) if o.isin == isin)

                if security_data.last_updated > last_order.timestamp:
                    logger.debug(
                        "Securities cache for %s (%s) is up-to-date", name, isin
                    )
                    continue

            update_cache = True

            logger.info("Fetching information for %s - %s", isin, name)
            if data := self._data_provider.get_security_data(isin):
                self._securities_data[isin] = data
            else:
                logger.warning("Failed to fetch information for %s - %s", isin, name)
                self._securities_data[isin] = SecurityData(name, [])

        if update_cache:
            self._update_cache()

    def _load_cache(self) -> None:
        if self._cache_file.exists():
            logger.info("Loading securities cache from %s", self._cache_file)

            with self._cache_file.open("r") as file:
                if data := yaml.load(file, Loader=yaml.FullLoader):
                    self._securities_data = data["securities"]

    def _update_cache(self) -> None:
        if self._cache_file.exists():
            logger.info("Updating securities cache on %s", self._cache_file)
        else:
            logger.info("Creating securities cache on %s", self._cache_file)

        self._cache_file.parent.mkdir(parents=True, exist_ok=True)
        securities_info = dict(sorted(self._securities_data.items()))
        data = {"version": VERSION, "securities": securities_info}

        with self._cache_file.open("w") as file:
            yaml.dump(data, file, sort_keys=False)

    def __getitem__(self, isin: ISIN) -> SecurityData:
        return self._securities_data[isin]
