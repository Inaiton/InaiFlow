"""Inventory valuation (pure) — WEIGHTED_AVG (perpetual moving average), FIFO, LIFO, STANDARD."""

from datetime import date
from decimal import Decimal

import pytest

from app.modules.accounts.valuation import Movement, value_stock

D = Decimal


def mv(day: int, kind: str, qty: str, rate: str = "0") -> Movement:
    return Movement(date=date(2026, 4, day), kind=kind, qty=D(qty), rate=D(rate))


def test_weighted_average_moving():
    r = value_stock("WEIGHTED_AVG", D("10"), D("100"), [mv(2, "INWARD", "10", "130"), mv(3, "OUTWARD", "5")])
    # avg after inward: (1000 + 1300) / 20 = 115 ; outward 5 at 115
    assert r.steps[1].cost == D("575.0000")
    assert r.closing_qty == D("15")
    assert r.closing_value == D("1725.0000")
    assert r.rate == D("115.0000")


def test_weighted_average_avg_changes_after_each_inward():
    r = value_stock(
        "WEIGHTED_AVG",
        D("0"),
        D("0"),
        [mv(1, "INWARD", "4", "10"), mv(2, "OUTWARD", "2"), mv(3, "INWARD", "2", "16"), mv(4, "OUTWARD", "3")],
    )
    # after 1: 4@10=40 ; out 2 -> 2@10=20 ; in 2@16 -> 4 qty 52 (avg 13) ; out 3 @13 = 39 -> 1 @13
    assert [s.cost for s in r.steps if s.kind == "OUTWARD"] == [D("20.0000"), D("39.0000")]
    assert (r.closing_qty, r.closing_value) == (D("1"), D("13.0000"))


def test_fifo_consumes_oldest_layers():
    r = value_stock("FIFO", D("10"), D("100"), [mv(2, "INWARD", "10", "130"), mv(3, "OUTWARD", "15")])
    # 10 @100 + 5 @130
    assert r.steps[1].cost == D("1650.0000")
    assert r.closing_qty == D("5")
    assert r.closing_value == D("650.0000")


def test_lifo_consumes_newest_layers():
    r = value_stock("LIFO", D("10"), D("100"), [mv(2, "INWARD", "10", "130"), mv(3, "OUTWARD", "15")])
    # 10 @130 + 5 @100
    assert r.steps[1].cost == D("1800.0000")
    assert r.closing_value == D("500.0000")


def test_standard_uses_opening_rate():
    r = value_stock("STANDARD", D("10"), D("100"), [mv(2, "INWARD", "10", "130"), mv(3, "OUTWARD", "5")])
    assert r.steps[1].cost == D("500.0000")
    assert r.closing_value == D("1500.0000")
    assert r.rate == D("100")


@pytest.mark.parametrize("method", ["WEIGHTED_AVG", "FIFO", "LIFO"])
def test_negative_stock_is_allowed_and_valued_at_last_rate(method):
    r = value_stock(method, D("2"), D("50"), [mv(2, "OUTWARD", "5")])
    assert r.closing_qty == D("-3")
    assert r.closing_value == D("-150.0000")
    assert r.went_negative


def test_negative_then_inward_recovers():
    r = value_stock(
        "FIFO", D("0"), D("0"), [mv(1, "INWARD", "2", "10"), mv(2, "OUTWARD", "3"), mv(3, "INWARD", "5", "12")]
    )
    # -1 @10 owed; inward 5@12 settles the shortfall first, leaving 4 @12
    assert r.closing_qty == D("4")
    assert r.closing_value == D("48.0000")


def test_no_movements_returns_opening():
    r = value_stock("FIFO", D("3"), D("7.5"), [])
    assert (r.closing_qty, r.closing_value, r.rate) == (D("3"), D("22.5000"), D("7.5000"))


def test_inward_with_explicit_amount_overrides_qty_rate():
    r = value_stock("WEIGHTED_AVG", D("0"), D("0"), [Movement(date(2026, 4, 1), "INWARD", D("3"), D("0"), D("100"))])
    assert r.closing_value == D("100.0000")
    assert r.rate == D("33.3333")


def test_unknown_method_rejected():
    with pytest.raises(ValueError):
        value_stock("AVERAGE", D("0"), D("0"), [])
