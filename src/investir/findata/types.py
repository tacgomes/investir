from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal

import yaml
from dateutil.parser import parse as parse_timestamp


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


@dataclass
class Split(yaml.YAMLObject):
    date_effective: datetime
    ratio: Decimal
    yaml_tag = "!split"

    @classmethod
    def from_yaml(cls, loader, node) -> "Split":
        value = loader.construct_scalar(node)
        timestamp, ratio = value.split(",")
        return Split(parse_timestamp(timestamp), Decimal(ratio))

    @classmethod
    def to_yaml(cls, dumper, data):
        return dumper.represent_scalar(
            cls.yaml_tag, f"{data.date_effective}, {data.ratio}"
        )

    def __eq__(self, other) -> bool:
        return self.date_effective == other.date_effective and self.ratio == other.ratio


@dataclass
class SecurityInfo(yaml.YAMLObject):
    name: str = ""
    splits: Sequence[Split] = field(default_factory=list)
    last_updated: datetime = field(default_factory=utcnow)
    yaml_tag = "!security"
