from datetime import datetime, timezone
from decimal import Decimal
from typing import Final


# Minimum timestamp for an order. Different rules apply on orders made
# before 6 April 2008. See:
# https://www.gov.uk/hmrc-internal-manuals/capital-gains-manual/cg51570
MIN_TIMESTAMP: Final = datetime(2008, 4, 6, tzinfo=timezone.utc)


def read_decimal(val: str, default: Decimal = Decimal("0.0")) -> Decimal:
    return Decimal(val) if val.strip() else default


def dict2str(d: dict[str, str]) -> str:
    return str({k: v for k, v in d.items() if v.strip()})
