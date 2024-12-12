import logging
from collections import defaultdict, namedtuple
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import TypeAlias

from investir.exceptions import AmbiguousTickerError, IncompleteRecordsError
from investir.findata import FinancialData
from investir.prettytable import PrettyTable
from investir.transaction import Acquisition, Disposal, Order
from investir.trhistory import TrHistory
from investir.typing import ISIN, Ticker, Year
from investir.utils import raise_or_warn

logger = logging.getLogger(__name__)


GroupKey = namedtuple("GroupKey", ["isin", "date", "type"])
GroupDict: TypeAlias = Mapping[GroupKey, Sequence[Order]]


def same_day_match(ord1: Acquisition, ord2: Disposal) -> bool:
    assert ord1.isin == ord2.isin
    return ord1.date == ord2.date


def thirty_days_match(ord1: Acquisition, ord2: Disposal) -> bool:
    assert ord1.isin == ord2.isin
    return ord2.date < ord1.date <= ord2.date + timedelta(days=30)


def gbp(amount):
    sign = "" if amount >= 0.0 else "-"
    return f"{sign}£{abs(amount):.2f}"


@dataclass
class CapitalGain:
    disposal: Disposal
    cost: Decimal
    acquisition_date: date | None = None

    @property
    def gain_loss(self) -> Decimal:
        # Disposal fees have been added to the `cost` so the gross
        # proceeds are used.
        return self.disposal.amount - self.cost

    @property
    def quantity(self) -> Decimal:
        if self.disposal.original_quantity is not None:
            return self.disposal.original_quantity
        return self.disposal.quantity

    @property
    def identification(self) -> str:
        match self.acquisition_date:
            case None:
                return "Section 104"
            case self.disposal.date:
                return "Same day"
            case _:
                return f"Bed & B. ({self.acquisition_date})"

    def __str__(self) -> str:
        return (
            f"{self.disposal.date} "
            f"{self.disposal.isin:<4} "
            f"quantity: {self.quantity}, "
            f"cost: £{self.cost:.2f}, proceeds: £{self.disposal.amount}, "
            f"gain: £{self.gain_loss:.2f}, "
            f"identification: {self.identification}"
        )


@dataclass
class CapitalGainsSummary:
    num_disposals: int
    disposal_proceeds: Decimal
    total_cost: Decimal
    total_gains: Decimal
    total_losses: Decimal

    @property
    def net_gains(self) -> Decimal:
        return self.total_gains - self.total_losses

    def __str__(self) -> str:
        return (
            f"{'Number of disposals:':40}{self.num_disposals:>10}      "
            f"{'Gains in the year, before losses:':34}{gbp(self.total_gains):>10}\n"
            f"{'Disposal proceeds:':40}{gbp(self.disposal_proceeds):>10}      "
            f"{'Losses in the year:':34}{gbp(self.total_losses):>10}\n"
            f"{'Allowable costs (incl. purchase price):':40}"
            f"{gbp(self.total_cost):>10}      "
            f"{'Net gain or loss:':34}{gbp(self.net_gains):>10}\n"
        )


@dataclass
class Section104Holding:
    quantity: Decimal
    cost: Decimal

    def __init__(self, _date: date, quantity: Decimal, cost: Decimal):
        self.quantity = quantity
        self.cost = cost

    def increase(self, _date: date, quantity: Decimal, cost: Decimal) -> None:
        self.quantity += quantity
        self.cost += cost

    def decrease(self, _date: date, quantity: Decimal, cost: Decimal) -> None:
        self.quantity -= quantity
        self.cost -= cost


class TaxCalculator:
    def __init__(self, tr_hist: TrHistory, findata: FinancialData) -> None:
        self._tr_hist = tr_hist
        self._findata = findata
        self._acquisitions: dict[ISIN, list[Acquisition]] = defaultdict(list)
        self._disposals: dict[ISIN, list[Disposal]] = defaultdict(list)
        self._holdings: dict[ISIN, Section104Holding] = {}
        self._capital_gains: dict[Year, list[CapitalGain]] = defaultdict(list)

    def capital_gains(self, tax_year: Year | None = None) -> Sequence[CapitalGain]:
        self._calculate_capital_gains()

        if tax_year is not None:
            return self._capital_gains.get(tax_year, [])

        return [cg for cg_group in self._capital_gains.values() for cg in cg_group]

    def holding(self, isin: ISIN) -> Section104Holding | None:
        self._calculate_capital_gains()
        return self._holdings.get(isin)

    def get_capital_gains_table(
        self,
        tax_year: Year,
        ticker_filter: Ticker | None,
        gains_only: bool,
        losses_only: bool,
    ) -> tuple[PrettyTable, CapitalGainsSummary]:
        assert not (gains_only and losses_only)

        self._calculate_capital_gains()

        table = PrettyTable(
            field_names=(
                "Disposal Date",
                "Identification",
                "Security Name",
                "ISIN",
                "Quantity",
                "Cost (£)",
                "Proceeds (£)",
                "Gain/loss (£)",
            ),
        )

        num_disposals = 0
        disposal_proceeds = total_cost = total_gains = total_losses = Decimal("0.0")

        for cg in self.capital_gains(tax_year):
            if ticker_filter is not None and cg.disposal.ticker != ticker_filter:
                continue

            if gains_only and cg.gain_loss < 0.0:
                continue

            if losses_only and cg.gain_loss > 0.0:
                continue

            table.add_row(
                [
                    cg.disposal.date,
                    cg.identification,
                    cg.disposal.name,
                    cg.disposal.isin,
                    cg.quantity,
                    cg.cost,
                    cg.disposal.amount,
                    cg.gain_loss,
                ]
            )

            num_disposals += 1
            disposal_proceeds += round(cg.disposal.amount, 2)
            total_cost += round(cg.cost, 2)
            if cg.gain_loss > 0.0:
                total_gains += cg.gain_loss
            else:
                total_losses += abs(cg.gain_loss)

        summary = CapitalGainsSummary(
            num_disposals, disposal_proceeds, total_cost, total_gains, total_losses
        )

        return table, summary

    def get_holdings_table(
        self, ticker_filter: Ticker | None = None, show_gain_loss: bool = False
    ) -> PrettyTable:
        self._calculate_capital_gains()

        table = PrettyTable(
            field_names=(
                "Security Name",
                "ISIN",
                "Cost (£)",
                "Quantity",
                "Current Value (£)",
                "Gain/Loss (£)",
                "Weight (%)",
            ),
            hidden_fields=(
                "Current Value (£)",
                "Gain/Loss (£)",
                "Weight (%)",
            )
            if not show_gain_loss
            else (),
            show_total_fields=(
                "Current Value (£)",
                "Gain/Loss (£)",
                "Weight (%)",
            )
            if show_gain_loss
            else (),
        )

        holdings = []

        if ticker_filter is None:
            holdings = sorted(
                self._holdings.items(), key=lambda x: x[1].cost, reverse=True
            )
        else:
            try:
                isin = self._tr_hist.get_ticker_isin(ticker_filter)
            except AmbiguousTickerError as e:
                logger.warning(e)
            else:
                if isin in self._holdings:
                    holdings = [(isin, self._holdings[isin])]

        holding2value = (
            {
                isin: value
                for isin, holding in holdings
                if (value := self._get_holding_value(isin, holding)) is not None
            }
            if show_gain_loss
            else {}
        )

        portfolio_value = sum(val for val in holding2value.values())
        last_idx = len(holdings) - 1

        for idx, (isin, holding) in enumerate(holdings):
            gain_loss: Decimal | None = None
            weight: Decimal | None = None

            if holding_value := holding2value.get(isin):
                gain_loss = holding.cost - holding_value
                weight = holding_value / portfolio_value * 100

            table.add_row(
                [
                    self._tr_hist.get_security_name(isin),
                    isin,
                    holding.cost,
                    holding.quantity,
                    holding_value,
                    gain_loss or "n/a",
                    weight or "n/a",
                ],
                divider=idx == last_idx,
            )

        return table

    def disposal_years(self) -> Sequence[Year]:
        self._calculate_capital_gains()
        return list(self._capital_gains.keys())

    def _calculate_capital_gains(self) -> None:
        if self._capital_gains or self._holdings:
            # Capital gains already calculated.
            return

        logger.info("Calculating capital gains")

        # First normalise the orders by retroactively adjusting their
        # share quantity for any eventual share sub-division or share
        # consolidation event.
        orders = self._normalise_orders(self._tr_hist.orders)

        # Group together orders that have the same isin, date and type.
        same_day = self._group_same_day(orders)

        for isin, name in self._tr_hist.securities:
            logger.debug("Calculating capital gains for %s (%s)", name, isin)

            # Merge orders that were issued in the same day and have
            # the same type, and place them in the acquisitions or
            # disposals bucket.
            self._merge_same_day(isin, same_day)

            # Match disposed shares with shares acquired in the same
            # day.
            self._match_shares(isin, same_day_match)

            # Match disposed shares with shares acquired up to 30 days
            # past the disposal date.
            self._match_shares(isin, thirty_days_match)

            # Process shares disposed from a Section 104 pool.
            self._process_section104_disposals(isin)

        # Capital gains are calculated ticker by ticker in order to be
        # able to show all the intermediary calculations grouped together
        # as a future improvement. However, for the report, it is more
        # intuitive to show the capital gain transactions ordered by
        # their disposal date.
        for year, events in self._capital_gains.items():
            self._capital_gains[year] = sorted(
                events, key=lambda te: (te.disposal.timestamp, te.disposal.isin)
            )

    def _normalise_orders(self, orders: Sequence[Order]) -> Sequence[Order]:
        return [
            o.adjust_quantity(self._findata.get_security_info(o.isin).splits)
            for o in orders
        ]

    def _group_same_day(self, orders: Sequence[Order]) -> GroupDict:
        same_day = defaultdict(list)
        for o in orders:
            key = GroupKey(o.isin, o.date, type(o))
            same_day[key].append(o)
        return same_day

    def _merge_same_day(self, isin: ISIN, same_day: GroupDict) -> None:
        security_orders = (
            orders for key, orders in same_day.items() if key.isin == isin
        )

        for orders in security_orders:
            if len(orders) > 1:
                order = Order.merge(*orders)
                logger.debug('    New "same-day" merged order: %s', order)
            else:
                order = orders[0]

            if isinstance(order, Acquisition):
                self._acquisitions[isin].append(order)
            elif isinstance(order, Disposal):
                self._disposals[isin].append(order)

    def _match_shares(
        self, isin: ISIN, match_fn: Callable[[Acquisition, Disposal], bool]
    ):
        acquisits = self._acquisitions[isin]
        disposals = self._disposals[isin]
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
                CapitalGain(d, a.total_cost + d.fees, a.date)
            )

        self._acquisitions[isin] = [o for o in acquisits if o not in matched]
        self._disposals[isin] = [o for o in disposals if o not in matched]

    def _process_section104_disposals(self, isin: ISIN) -> None:
        security_orders = sorted(
            [*self._acquisitions[isin], *self._disposals[isin]],
            key=lambda order: order.date,
        )

        for order in security_orders:
            holding = self._holdings.get(isin)

            if isinstance(order, Acquisition):
                if holding is not None:
                    holding.increase(order.date, order.quantity, order.total_cost)
                else:
                    self._holdings[isin] = Section104Holding(
                        order.date, order.quantity, order.total_cost
                    )
            elif isinstance(order, Disposal):
                if holding is not None:
                    allowable_cost = holding.cost * order.quantity / holding.quantity

                    holding.decrease(order.date, order.quantity, allowable_cost)

                    if holding.quantity < 0.0:
                        raise_or_warn(
                            IncompleteRecordsError(
                                isin, self._tr_hist.get_security_name(isin) or "?"
                            )
                        )
                        logger.warning("Not calculating holding for %s", isin)
                        del self._holdings[isin]
                        break

                    if holding.quantity == Decimal("0.0"):
                        del self._holdings[isin]

                    self._capital_gains[order.tax_year()].append(
                        CapitalGain(order, allowable_cost + order.fees)
                    )
                else:
                    raise_or_warn(
                        IncompleteRecordsError(
                            isin, self._tr_hist.get_security_name(isin) or "?"
                        )
                    )
                    logger.warning("Not calculating holding for %s", isin)
                    break

    def _get_holding_value(
        self, isin: ISIN, holding: Section104Holding
    ) -> Decimal | None:
        if (price := self._findata.get_security_price(isin)) and (
            price_gbp := self._findata.convert_currency(price.amount, price.currency)
        ):
            return holding.quantity * price_gbp

        return None
