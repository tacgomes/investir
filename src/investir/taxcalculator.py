import logging
from collections import defaultdict, namedtuple
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, TypeAlias, TypeVar, cast

from moneyed import GBP, Money

from investir.config import config
from investir.const import BASE_CURRENCY
from investir.exceptions import IncompleteRecordsError, InvestirError
from investir.fees import scalar_op
from investir.findata import FinancialData
from investir.transaction import Acquisition, Disposal, Order
from investir.trhistory import TransactionHistory
from investir.typing import ISIN, TaxYear
from investir.utils import raise_or_warn

logger = logging.getLogger(__name__)

FuncType = TypeVar("FuncType", bound=Callable[..., Any])

GroupKey = namedtuple("GroupKey", ["isin", "date", "type"])
GroupDict: TypeAlias = Mapping[GroupKey, Sequence[Order]]


def same_day_match(ord1: Acquisition, ord2: Disposal) -> bool:
    assert ord1.isin == ord2.isin
    return ord1.date == ord2.date


def thirty_days_match(ord1: Acquisition, ord2: Disposal) -> bool:
    assert ord1.isin == ord2.isin
    return ord2.date < ord1.date <= ord2.date + timedelta(days=30)


@dataclass
class CapitalGain:
    disposal: Disposal
    cost: Decimal
    acquisition_date: date | None = None

    @property
    def gain_loss(self) -> Decimal:
        # Disposal fees have been added to the `cost` so the gross
        # proceeds are used.
        return (
            self.disposal.gross_proceeds
            - Money(self.cost, self.disposal.total.currency)
        ).amount

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
            f"cost: £{self.cost:.2f}, "
            f"proceeds: £{self.disposal.gross_proceeds.amount}, "
            f"gain: £{self.gain_loss:.2f}, "
            f"identification: {self.identification}"
        )


@dataclass
class Section104Holding:
    isin: ISIN
    cost: Decimal
    quantity: Decimal

    def add(self, cost: Decimal, quantity: Decimal) -> None:
        self.cost += cost
        self.quantity += quantity

    def remove(self, cost: Decimal, quantity: Decimal) -> None:
        self.cost -= cost
        self.quantity -= quantity


def lazycalc(func: FuncType) -> FuncType:
    def _wrapper(self, *args, **kwargs):
        if not self._capital_gains and not self._holdings:
            self._calculate_capital_gains()
        return func(self, *args, **kwargs)

    return cast(FuncType, _wrapper)


class TaxCalculator:
    def __init__(self, trhistory: TransactionHistory, findata: FinancialData) -> None:
        self._trhistory = trhistory
        self._findata = findata
        self._acquisitions: dict[ISIN, list[Acquisition]] = defaultdict(list)
        self._disposals: dict[ISIN, list[Disposal]] = defaultdict(list)
        self._holdings: dict[ISIN, Section104Holding] = {}
        self._capital_gains: dict[TaxYear, list[CapitalGain]] = defaultdict(list)

    @lazycalc
    def capital_gains(self, tax_year: TaxYear | None = None) -> Sequence[CapitalGain]:
        if tax_year is not None:
            return self._capital_gains.get(tax_year, [])

        return [cg for cg_group in self._capital_gains.values() for cg in cg_group]

    @property
    @lazycalc
    def holdings(self) -> Sequence[Section104Holding]:
        return list(self._holdings.values())

    @lazycalc
    def holding(self, isin: ISIN) -> Section104Holding | None:
        return self._holdings.get(isin)

    @lazycalc
    def get_holding_value(self, isin: ISIN) -> Decimal | None:
        holding = self._holdings[isin]
        security_name = self._trhistory.get_security_name(isin) or ""
        if (price := self._findata.get_security_price(isin, security_name)) and (
            price_base_currency := self._findata.convert_money(price, BASE_CURRENCY)
        ):
            return holding.quantity * price_base_currency.amount

        return None

    @lazycalc
    def disposal_years(self) -> Sequence[TaxYear]:
        return list(self._capital_gains.keys())

    def _calculate_capital_gains(self) -> None:
        logger.info("Calculating capital gains")

        orders = self._trhistory.orders

        # Convert acquisitions and disposals not realised in pound
        # sterling to use monetary values specified in this currency.
        orders = [self._convert_to_sterling(o) for o in orders]

        # Exclude forex fees from the `total` and `fees` fields if
        # necessary.
        if config.include_fx_fees is False:
            orders = [self._exclude_fx_fees(o) for o in orders]

        # Normalise the orders by retroactively adjusting their share
        # quantity for any eventual share sub-division or share
        # consolidation event.
        orders = [self._normalise_quantity(o) for o in orders]

        # Group together orders that have the same isin, date and type.
        same_day = self._group_same_day(orders)

        for isin, name in self._trhistory.securities:
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

    def _convert_to_sterling(self, order: Order) -> Order:
        def convert(m):
            if m is None:
                return m
            if (new_m := self._findata.convert_money(m, GBP, order.date)) is None:
                raise InvestirError(
                    f"Failed to get historical exchange rate for "
                    f"GBP-{m.currency} on {order.date}"
                )
            return new_m

        try:
            fees_currency = order.fees.total.currency
        except TypeError:
            # Multiple fees in different currencies: conversion needed.
            fees_currency = None

        if (order.total.currency, fees_currency) != (GBP, GBP):
            total = convert(order.total)
            fees = scalar_op(convert, order.fees)
            return replace(
                order,
                total=total,
                fees=fees,
                notes="Conversion to sterling from order {order.number}",
            )

        return order

    def _exclude_fx_fees(self, order: Order) -> Order:
        if order.fees.forex:
            if isinstance(order, Acquisition):
                total = order.total - order.fees.forex
            else:
                total = order.total + order.fees.forex

            return replace(
                order,
                total=total,
                fees=replace(order.fees, forex=None),
                notes="Forex fees removed from order {order.number}",
            )

        return order

    def _normalise_quantity(self, order: Order) -> Order:
        security_info = self._findata.get_security_info(
            order.isin, order.name, order.timestamp
        )
        return order.adjust_quantity(security_info.splits)

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
                CapitalGain(d, a.total.amount + d.fees.total.amount, a.date)
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
                    holding.add(order.total.amount, order.quantity)
                else:
                    self._holdings[isin] = Section104Holding(
                        isin, order.total.amount, order.quantity
                    )
            elif isinstance(order, Disposal):
                if holding is not None:
                    allowable_cost = holding.cost * order.quantity / holding.quantity

                    holding.remove(allowable_cost, order.quantity)

                    if holding.quantity < 0.0:
                        raise_or_warn(
                            IncompleteRecordsError(
                                isin, self._trhistory.get_security_name(isin) or "?"
                            )
                        )
                        logger.warning("Not calculating holding for %s", isin)
                        del self._holdings[isin]
                        break

                    if holding.quantity == Decimal("0.0"):
                        del self._holdings[isin]

                    self._capital_gains[order.tax_year()].append(
                        CapitalGain(order, allowable_cost + order.fees.total.amount)
                    )
                else:
                    raise_or_warn(
                        IncompleteRecordsError(
                            isin, self._trhistory.get_security_name(isin) or "?"
                        )
                    )
                    logger.warning("Not calculating holding for %s", isin)
                    break
