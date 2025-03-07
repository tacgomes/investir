from collections.abc import Mapping, Sequence, ValuesView
from typing import NamedTuple, TypeVar

from investir.exceptions import AmbiguousTickerError
from investir.transaction import (
    Dividend,
    Interest,
    Order,
    Transaction,
    Transfer,
)
from investir.typing import ISIN, Ticker

T = TypeVar("T", bound=Transaction)


def unique_and_sorted(transactions: Sequence[T] | None) -> Sequence[T]:
    """Remove duplicated transactions and sort them by timestamp."""
    return sorted(set(transactions or []), key=lambda tr: tr.timestamp)


class Security(NamedTuple):
    isin: ISIN
    name: str = ""


class TransactionHistory:
    def __init__(
        self,
        *,
        orders: Sequence[Order] | None = None,
        dividends: Sequence[Dividend] | None = None,
        transfers: Sequence[Transfer] | None = None,
        interest: Sequence[Interest] | None = None,
    ) -> None:
        self._orders = unique_and_sorted(orders)
        self._dividends = unique_and_sorted(dividends)
        self._transfers = unique_and_sorted(transfers)
        self._interest = unique_and_sorted(interest)
        self._securities: Mapping[ISIN, Security] = {}

    @property
    def orders(self) -> Sequence[Order]:
        return self._orders

    @property
    def dividends(self) -> Sequence[Dividend]:
        return self._dividends

    @property
    def transfers(self) -> Sequence[Transfer]:
        return self._transfers

    @property
    def interest(self) -> Sequence[Interest]:
        return self._interest

    @property
    def securities(self) -> ValuesView[Security]:
        return self._securities_map().values()

    def get_security_name(self, isin: ISIN) -> str | None:
        security = self._securities_map().get(isin)
        return security.name if security else None

    def get_ticker_isin(self, ticker: Ticker) -> ISIN | None:
        isins = set(o.isin for o in self._orders if o.ticker == ticker)

        match len(isins):
            case 0:
                return None
            case 1:
                return next(iter(isins))
            case _:
                raise AmbiguousTickerError(ticker)

    def _securities_map(self) -> Mapping[ISIN, Security]:
        if not self._securities:
            self._securities = {
                o.isin: Security(o.isin, o.name)
                for o in sorted(self._orders, key=lambda o: o.name)
            }
        return self._securities
