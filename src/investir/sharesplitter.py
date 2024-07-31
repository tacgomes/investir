import logging

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from functools import reduce
import operator
from pathlib import Path

from dateutil.parser import parse as parse_timestamp
from platformdirs import user_cache_dir
import yaml
import yfinance

from .transaction import Order
from .trhistory import TrHistory
from .typing import ISIN

logger = logging.getLogger(__name__)

VERSION = 1
DEFAULT_CACHE_DIR = Path(user_cache_dir()) / "investir"
DEFAULT_CACHE_FILENAME = "securities.yaml"


@dataclass
class Split(yaml.YAMLObject):
    date_effective: datetime
    ratio: Decimal
    yaml_tag = "!split"

    @classmethod
    def from_yaml(cls, loader, node):
        value = loader.construct_scalar(node)
        timestamp, ratio = value.split(",")
        return Split(parse_timestamp(timestamp), Decimal(ratio))

    @classmethod
    def to_yaml(cls, dumper, data):
        return dumper.represent_scalar(
            cls.yaml_tag, f"{data.date_effective}, {data.ratio}"
        )


@dataclass
class SecurityInfo(yaml.YAMLObject):
    name: str = ""
    splits: list[Split] = field(default_factory=list)
    last_updated = datetime.fromtimestamp(0, timezone.utc)
    yaml_tag = "!security"


class ShareSplitter:
    def __init__(self, tr_hist: TrHistory, cache_file: Path | None = None) -> None:
        self._tr_hist = tr_hist
        self._cache_file = cache_file
        if self._cache_file is None:
            self._cache_file = DEFAULT_CACHE_DIR / DEFAULT_CACHE_FILENAME
        self._securities_info: dict[ISIN, SecurityInfo] = {}

        self._initialise()

    def splits(self, isin: ISIN) -> list[Split]:
        security_info = self._securities_info.get(isin)
        return security_info.splits if security_info else []

    def adjust_quantity(self, order: Order) -> Order:
        split_ratios = [
            split.ratio
            for split in self.splits(order.isin)
            if order.timestamp < split.date_effective
        ]

        if not split_ratios:
            return order

        quantity = reduce(operator.mul, [order.quantity] + split_ratios)

        return type(order)(
            order.timestamp,
            isin=order.isin,
            ticker=order.ticker,
            name=order.name,
            amount=order.amount,
            quantity=quantity,
            original_quantity=order.quantity,
            fees=order.fees,
            notes=(
                f"Adjusted from order {order.id} after applying the "
                f"following split ratios: {', '.join(map(str, split_ratios))}"
            ),
        )

    def _initialise(self):
        self._load_cache()

        orders = self._tr_hist.orders()
        update_cache = False

        for isin, name in self._tr_hist.securities():
            security_info = self._securities_info.setdefault(
                isin, SecurityInfo(name=name)
            )
            last_order = next(o for o in reversed(orders) if o.isin == isin)

            if security_info.last_updated > last_order.timestamp:
                logging.debug("Securities cache for %s (%s) is up-to-date", name, isin)
                continue

            logging.info("Fetching information for %s (%s)", name, isin)

            splits = yfinance.Ticker(isin).splits

            security_info.splits = []
            security_info.last_updated = datetime.now(timezone.utc).replace(
                microsecond=0
            )
            update_cache = True

            for date_str, ratio_str in splits.items():
                date_effective = date_str.to_pydatetime()
                ratio = Decimal(ratio_str)
                security_info.splits.append(Split(date_effective, ratio))

        if update_cache:
            self._update_cache()

    def _load_cache(self):
        if self._cache_file.exists():
            logging.info("Loading securities cache from %s", self._cache_file)

            with self._cache_file.open("r") as file:
                data = yaml.load(file, Loader=yaml.FullLoader)
                self._securities_info = data["securities"]

    def _update_cache(self):
        if self._cache_file.exists():
            logging.info("Updating securities cache on %s", self._cache_file)
        else:
            logging.info("Creating securities cache on %s", self._cache_file)

        self._cache_file.parent.mkdir(parents=True, exist_ok=True)
        securities_info = dict(sorted(self._securities_info.items()))
        data = {"version": VERSION, "securities": securities_info}

        with self._cache_file.open("w") as file:
            yaml.dump(data, file, sort_keys=False)
