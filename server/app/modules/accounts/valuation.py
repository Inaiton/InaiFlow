"""Inventory valuation — pure functions (no DB). Plan §3.8.

* ``WEIGHTED_AVG`` perpetual moving average: every inward re-computes the average; outwards are costed at the
  average in force at that moment.
* ``FIFO`` / ``LIFO``: inward creates a cost layer; outward consumes the oldest / newest layers.
* ``STANDARD``: everything at the item's standard rate (= ``opening_rate``).

Negative stock is allowed (reported in exceptions): a shortfall is valued at the last known rate; the next
inward first settles the shortfall (FIFO/LIFO) or simply re-averages (WEIGHTED_AVG).
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from app.core.money import ZERO, q4

METHODS = ("WEIGHTED_AVG", "FIFO", "LIFO", "STANDARD")


@dataclass(frozen=True, slots=True)
class Movement:
    date: date
    kind: str  # INWARD | OUTWARD
    qty: Decimal
    rate: Decimal = ZERO
    amount: Decimal | None = None  # inward value (defaults to qty * rate); ignored for outward
    ref: object = None  # caller's handle (voucher id, godown...) echoed back in the step


@dataclass(frozen=True, slots=True)
class Step:
    movement: Movement
    kind: str
    qty: Decimal
    cost: Decimal  # inward value or outward consumption cost
    balance_qty: Decimal
    balance_value: Decimal
    rate: Decimal  # running unit rate after the movement


@dataclass(slots=True)
class Valuation:
    method: str
    closing_qty: Decimal
    closing_value: Decimal
    rate: Decimal
    steps: list[Step] = field(default_factory=list)
    went_negative: bool = False


def _rate(qty: Decimal, value: Decimal, fallback: Decimal) -> Decimal:
    return q4(value / qty) if qty > 0 else fallback


def value_stock(method: str, opening_qty: Decimal, opening_rate: Decimal, movements: list[Movement]) -> Valuation:
    """Value ``movements`` (already in chronological order) starting from the opening balance."""
    if method not in METHODS:
        raise ValueError(f"unknown valuation method {method!r}")
    if method == "STANDARD":
        return _standard(opening_qty, opening_rate, movements)
    if method == "WEIGHTED_AVG":
        return _weighted(opening_qty, opening_rate, movements)
    return _layers(method, opening_qty, opening_rate, movements)


def _inward_value(m: Movement) -> Decimal:
    return q4(m.amount if m.amount is not None else m.qty * m.rate)


def _standard(opening_qty: Decimal, std: Decimal, movements: list[Movement]) -> Valuation:
    qty = opening_qty
    res = Valuation("STANDARD", qty, q4(qty * std), std)
    for m in movements:
        cost = q4(m.qty * std)
        qty = qty + m.qty if m.kind == "INWARD" else qty - m.qty
        res.went_negative |= qty < 0
        res.steps.append(Step(m, m.kind, m.qty, cost, qty, q4(qty * std), std))
    res.closing_qty, res.closing_value = qty, q4(qty * std)
    return res


def _weighted(opening_qty: Decimal, opening_rate: Decimal, movements: list[Movement]) -> Valuation:
    qty, value = opening_qty, q4(opening_qty * opening_rate)
    last_rate = q4(opening_rate)
    res = Valuation("WEIGHTED_AVG", qty, value, last_rate)
    for m in movements:
        if m.kind == "INWARD":
            cost = _inward_value(m)
            qty, value = qty + m.qty, value + cost
            if m.qty > 0:
                last_rate = q4(cost / m.qty)
            if qty > 0:
                last_rate = q4(value / qty)
            else:
                value = q4(qty * last_rate)
        else:
            avg = _rate(qty, value, last_rate)
            cost = q4(m.qty * avg)
            qty, value = qty - m.qty, value - cost
            last_rate = avg
            if qty <= 0:
                value = q4(qty * last_rate)
        res.went_negative |= qty < 0
        res.steps.append(Step(m, m.kind, m.qty, cost, qty, q4(value), last_rate))
    res.closing_qty, res.closing_value, res.rate = qty, q4(value), _rate(qty, value, last_rate)
    return res


def _layers(method: str, opening_qty: Decimal, opening_rate: Decimal, movements: list[Movement]) -> Valuation:
    layers: deque[list[Decimal]] = deque()  # [qty, rate]; a single negative layer represents a shortfall
    if opening_qty != 0:
        layers.append([opening_qty, q4(opening_rate)])
    last_rate = q4(opening_rate)

    def totals() -> tuple[Decimal, Decimal]:
        return sum((lq for lq, _ in layers), ZERO), q4(sum((lq * lr for lq, lr in layers), ZERO))

    res = Valuation(method, *totals(), last_rate)
    for m in movements:
        if m.kind == "INWARD":
            cost = _inward_value(m)
            rate = q4(cost / m.qty) if m.qty > 0 else last_rate
            remaining = m.qty
            if layers and layers[0][0] < 0:  # settle a shortfall first
                short = -layers[0][0]
                used = min(short, remaining)
                layers[0][0] += used
                remaining -= used
                if layers[0][0] == 0:
                    layers.popleft()
            if remaining > 0:
                layers.append([remaining, rate])
            last_rate = rate
        else:
            need, cost = m.qty, ZERO
            while need > 0 and layers and layers[0][0] > 0:
                layer = layers[0] if method == "FIFO" else layers[-1]
                used = min(layer[0], need)
                cost += used * layer[1]
                layer[0] -= used
                need -= used
                last_rate = layer[1]
                if layer[0] == 0:
                    (layers.popleft if method == "FIFO" else layers.pop)()
            if need > 0:  # shortfall -> negative layer at the last known rate
                cost += need * last_rate
                if layers and layers[0][0] < 0:
                    layers[0][0] -= need
                else:
                    layers.appendleft([-need, last_rate])
            cost = q4(cost)
        qty, value = totals()
        res.went_negative |= qty < 0
        res.steps.append(Step(m, m.kind, m.qty, cost, qty, value, _rate(qty, value, last_rate)))
    qty, value = totals()
    res.closing_qty, res.closing_value, res.rate = qty, value, _rate(qty, value, last_rate)
    return res
