from datetime import datetime, timezone
from typing import Final

from moneyed import get_currency

# Minimum timestamp for an order. Different rules apply on orders made
# before 6 April 2008. See:
# https://www.gov.uk/hmrc-internal-manuals/capital-gains-manual/cg51570
MIN_TIMESTAMP: Final = datetime(2008, 4, 6, tzinfo=timezone.utc)

BASE_CURRENCY: Final = get_currency("GBP")
