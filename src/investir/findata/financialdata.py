import logging
from pathlib import Path
from typing import Final

import yaml

from investir.findata.dataprovider import DataProviderError, SecurityInfoProvider
from investir.findata.types import SecurityInfo
from investir.trhistory import TrHistory
from investir.typing import ISIN

logger = logging.getLogger(__name__)


class FinancialData:
    VERSION: Final = 1

    def __init__(
        self,
        security_info_provider: SecurityInfoProvider | None,
        tr_hist: TrHistory,
        cache_file: Path,
    ) -> None:
        self._security_info_provider = security_info_provider
        self._tr_hist = tr_hist
        self._cache_file = cache_file
        self._security_info: dict[ISIN, SecurityInfo] = {}

        self._initialise()

    def _initialise(self) -> None:
        self._load_cache()

        orders = self._tr_hist.orders
        update_cache = False

        for isin, name in self._tr_hist.securities:
            if (security_info := self._security_info.get(isin)) is not None:
                last_order = next(o for o in reversed(orders) if o.isin == isin)

                if security_info.last_updated > last_order.timestamp:
                    logger.debug(
                        "Securities cache for %s (%s) is up-to-date", name, isin
                    )
                    continue

            self._security_info[isin] = SecurityInfo(name, [])
            update_cache = True

            if self._security_info_provider is not None:
                logger.info("Fetching information for %s - %s", isin, name)
                try:
                    self._security_info[isin] = self._security_info_provider.fech_info(
                        isin
                    )
                except DataProviderError as ex:
                    logger.warning(str(ex))

        if update_cache:
            self._update_cache()

    def _load_cache(self) -> None:
        if self._cache_file.exists():
            logger.info("Loading securities cache from %s", self._cache_file)

            with self._cache_file.open("r") as file:
                if data := yaml.load(file, Loader=yaml.FullLoader):
                    self._security_info = data["securities"]

    def _update_cache(self) -> None:
        if self._cache_file.exists():
            logger.info("Updating securities cache on %s", self._cache_file)
        else:
            logger.info("Creating securities cache on %s", self._cache_file)

        self._cache_file.parent.mkdir(parents=True, exist_ok=True)
        securities_info = dict(sorted(self._security_info.items()))
        data = {"version": self.__class__.VERSION, "securities": securities_info}

        with self._cache_file.open("w") as file:
            yaml.dump(data, file, sort_keys=False)

    def __getitem__(self, isin: ISIN) -> SecurityInfo:
        return self._security_info[isin]
