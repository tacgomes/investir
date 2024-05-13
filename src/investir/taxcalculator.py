import logging

from collections import defaultdict, namedtuple
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Callable

from .transaction import Order, Acquisition, Disposal
from .trhistory import TrHistory

logger = logging.getLogger(__name__)


GroupKey = namedtuple('GroupKey', ['ticker', 'date', 'type'])


def same_day_match(ord1: Acquisition, ord2: Disposal) -> bool:
    assert ord1.ticker == ord2.ticker
    return ord1.date == ord2.date


def thirty_days_match(ord1: Acquisition, ord2: Disposal) -> bool:
    assert ord1.ticker == ord2.ticker
    return ord2.date < ord1.date <= ord2.date + timedelta(days=30)


@dataclass
class CapitalGain:
    disposal: Disposal
    cost: Decimal
    date_acquired: date | None = None

    @property
    def gain_loss(self) -> Decimal:
        # Disposal fees have been added to the `cost` so the gross
        # proceeds are used.
        return self.disposal.amount - self.cost

    def __str__(self) -> str:
        return (
            f'{self.disposal.date} '
            f'{self.disposal.ticker:<4} '
            f'quantity: {self.disposal.quantity}, '
            f'cost: £{self.cost:.2f}, proceeds: £{self.disposal.amount}, '
            f'gain: £{self.gain_loss:.2f} '
            f'({self.date_acquired or "Section 104"})')


@dataclass
class Section104Holding:
    quantity: Decimal
    cost: Decimal

    def __init__(self, _date: date, quantity: Decimal, cost: Decimal):
        self.quantity = quantity
        self.cost = cost

    def increase(
            self, _date: date, quantity: Decimal, cost: Decimal) -> None:
        self.quantity += quantity
        self.cost += cost

    def decrease(
            self, _date: date, quantity: Decimal, cost: Decimal) -> None:
        self.quantity -= quantity
        self.cost -= cost

        if self.quantity < 0.0:
            raise RuntimeError(
                'Section104Holding: share quantity cannot be negative')


class TaxCalculator:
    def __init__(self, tr_hist: TrHistory) -> None:
        self._tr_hist = tr_hist
        self._same_day_orders: dict[GroupKey, list[Order]] = defaultdict(list)
        self._acquisitions: dict[str, list[Acquisition]] = defaultdict(list)
        self._disposals: dict[str, list[Disposal]] = defaultdict(list)
        self._holdings: dict[str, Section104Holding] = {}
        self._capital_gains: dict[int, list[CapitalGain]] = defaultdict(list)

        self._calculate_capital_gains()

    def capital_gains(self, tax_year: int | None = None) -> list[CapitalGain]:
        if tax_year is not None:
            return self._capital_gains.get(tax_year, [])

        return [
            cg
            for cg_group in self._capital_gains.values()
            for cg in cg_group]

    def holdings(self) -> dict[str, Section104Holding]:
        return self._holdings

    def _calculate_capital_gains(self) -> None:
        logging.info('Calculating capital gains')

        # Group together orders that have the same ticker, date and type.
        self._group_same_day_orders()

        tickers = sorted(set(
            order.ticker for order in self._tr_hist.orders()))

        for ticker in tickers:
            logging.debug('Calculating capital gains for %s', ticker)

            # Merge orders that were issued in the same day and have
            # the same type, and place them in the acquisitions or
            # disposals bucket.
            self._merge_same_day_orders(ticker)

            # Match disposed shares with shares acquired in the same
            # day.
            self._match_shares(ticker, same_day_match)

            # Match disposed shares with shares acquired up to 30 days
            # past the disposal date.
            self._match_shares(ticker, thirty_days_match)

            # Process shares disposed from a Section 104 pool.
            self._process_section104_disposals(ticker)

        # Capital gains are calculated ticker by ticker in order to be
        # able to show all the intermediary calculations grouped together
        # as a future improvement. However, for the report, it is more
        # intuitive to show the capital gain transactions ordered by
        # their disposal date.
        for year, events in self._capital_gains.items():
            self._capital_gains[year] = sorted(
                events,
                key=lambda te: (te.disposal.timestamp, te.disposal.ticker))

    def _group_same_day_orders(self) -> None:
        for o in self._tr_hist.orders():
            key = GroupKey(o.ticker, o.date, type(o))
            self._same_day_orders[key].append(o)

    def _merge_same_day_orders(self, ticker: str) -> None:
        ticker_orders = (
            orders for key, orders in self._same_day_orders.items()
            if key.ticker == ticker)

        for orders in ticker_orders:
            if len(orders) > 1:
                order = Order.merge(*orders)
                logging.debug('    New "same-day" merged order: %s', order)
            else:
                order = orders[0]

            if isinstance(order, Acquisition):
                self._acquisitions[ticker].append(order)
            elif isinstance(order, Disposal):
                self._disposals[ticker].append(order)

    def _match_shares(self,
                      ticker: str,
                      match_fn: Callable[[Acquisition, Disposal], bool]):
        acquisits = self._acquisitions[ticker]
        disposals = self._disposals[ticker]
        matched: set[Order] = set()

        a_idx = 0
        d_idx = 0

        while d_idx < len(disposals):
            if a_idx == len(acquisits):
                a_idx = 0
                d_idx += 1
                continue

            a = acquisits[a_idx]
            d = disposals[d_idx]

            if not match_fn(a, d) or a in matched:
                a_idx += 1
                continue

            matched.add(a)
            matched.add(d)

            if a.quantity > d.quantity:
                a, acquisits[a_idx] = a.split(d.quantity)
                a_idx = 0
                d_idx += 1
            elif d.quantity > a.quantity:
                d, disposals[d_idx] = d.split(a.quantity)
                a_idx += 1
            else:
                a_idx = 0
                d_idx += 1

            self._capital_gains[d.tax_year()].append(
                CapitalGain(d, a.total_cost + d.fees, a.date))

        self._acquisitions[ticker] = [o for o in acquisits if o not in matched]
        self._disposals[ticker] = [o for o in disposals if o not in matched]

    def _process_section104_disposals(self, ticker) -> None:
        ticker_orders = sorted([
            *self._acquisitions[ticker], *self._disposals[ticker]],
            key=lambda order: order.date)

        for order in ticker_orders:
            holding = self._holdings.get(ticker)

            if isinstance(order, Acquisition):
                if holding is not None:
                    holding.increase(
                        order.date, order.quantity, order.total_cost)
                else:
                    self._holdings[ticker] = Section104Holding(
                        order.date, order.quantity, order.total_cost)
            elif isinstance(order, Disposal):
                if holding is not None:
                    allowable_cost = (
                        holding.cost * order.quantity / holding.quantity)

                    holding.decrease(
                        order.date, order.quantity, allowable_cost)

                    if holding.quantity == Decimal('0.0'):
                        del self._holdings[ticker]

                    self._capital_gains[order.tax_year()].append(
                        CapitalGain(order, allowable_cost + order.fees))
                else:
                    raise RuntimeError(
                        'Processing disposal order without previous '
                        'acquisitions found')
