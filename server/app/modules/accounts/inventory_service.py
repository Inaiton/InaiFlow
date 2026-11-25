"""Inventory valuation over the DB (uses the pure ``valuation`` module), stock summary and item movements.

Opening stock of an item is held in the MAIN system godown. Valuation is per item across all godowns;
godown-filtered views value the godown quantity at the item's running rate.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import TenantContext
from app.core.errors import NotFoundError, ValidationFailedError
from app.core.money import ZERO, q4
from app.modules.accounts import repository as repo
from app.modules.accounts.models import Godown, StockGroup, StockItem
from app.modules.accounts.schemas import StockMovementOut, StockSummaryRow
from app.modules.accounts.valuation import Movement, Valuation, value_stock


def _movements(rows: list) -> dict[uuid.UUID, list[Movement]]:
    out: dict[uuid.UUID, list[Movement]] = defaultdict(list)
    for r in rows:
        vie = r[0]
        out[vie.stock_item_id].append(Movement(r.voucher_date, vie.movement_type, vie.quantity, vie.rate, vie.amount,
                                               ref=r))  # fmt: skip
    return out


async def valuations(
    db: AsyncSession, org_id: uuid.UUID, items: list[StockItem], as_of: date | None = None
) -> dict[uuid.UUID, Valuation]:
    if not items:
        return {}
    by_item = _movements(await repo.stock_movements(db, org_id, [i.id for i in items], date_to=as_of))
    return {i.id: value_stock(i.valuation_method, i.opening_qty, i.opening_rate, by_item.get(i.id, [])) for i in items}


async def total_stock_value(db: AsyncSession, org_id: uuid.UUID, as_of: date | None) -> Decimal:
    """Closing stock (inventory valuation) of every STOCK_ITEM as of a date; None = all time."""
    items = [i for i in await repo.list_all(db, StockItem, org_id, StockItem.name) if i.target_type == "STOCK_ITEM"]
    vals = await valuations(db, org_id, items, as_of)
    return sum((v.closing_value for v in vals.values()), ZERO)


async def godown_quantities(db: AsyncSession, ctx: TenantContext, godown_id: uuid.UUID, as_of: date | None
                            ) -> dict[uuid.UUID, Decimal]:  # fmt: skip
    gd = await repo.get(db, Godown, ctx.org_id, godown_id)
    if gd is None:
        raise NotFoundError()
    qty: dict[uuid.UUID, Decimal] = defaultdict(lambda: ZERO)
    if gd.system_code == "MAIN":
        for i in await repo.list_all(db, StockItem, ctx.org_id, StockItem.name):
            qty[i.id] += i.opening_qty
    for r in await repo.stock_movements(db, ctx.org_id, None, date_to=as_of):
        vie = r[0]
        if vie.godown_id == godown_id:
            qty[vie.stock_item_id] += vie.quantity if vie.movement_type == "INWARD" else -vie.quantity
    return qty


async def stock_summary(
    db: AsyncSession, ctx: TenantContext, *, as_of: date | None, godown_id: uuid.UUID | None,
    stock_group_id: uuid.UUID | None, visible: set[uuid.UUID] | None = None,
) -> list[StockSummaryRow]:  # fmt: skip
    rows = await repo.items_with_groups(db, ctx.org_id)
    items = [r[0] for r in rows if r[0].target_type == "STOCK_ITEM"]
    if stock_group_id:
        groups = await repo.list_all(db, StockGroup, ctx.org_id, StockGroup.name)
        wanted, stack = set(), [stock_group_id]
        while stack:
            gid = stack.pop()
            wanted.add(gid)
            stack.extend(g.id for g in groups if g.parent_id == gid and g.id not in wanted)
        items = [i for i in items if i.stock_group_id in wanted]
    if visible is not None:
        items = [i for i in items if i.id in visible]
    group_names = {r[0].id: r.group_name for r in rows}
    vals = await valuations(db, ctx.org_id, items, as_of)
    gq = await godown_quantities(db, ctx, godown_id, as_of) if godown_id else None
    out = []
    for i in items:
        v = vals[i.id]
        qty = gq.get(i.id, ZERO) if gq is not None else v.closing_qty
        value = q4(qty * v.rate) if gq is not None else v.closing_value
        below = i.reorder_level is not None and qty < i.reorder_level
        out.append(StockSummaryRow(stock_item_id=i.id, name=i.name, stock_group_name=group_names.get(i.id),
                                   uom=i.uom_primary, valuation_method=i.valuation_method, quantity=qty, rate=v.rate,
                                   value=value, reorder_level=i.reorder_level, below_reorder=below))  # fmt: skip
    return out


async def item_movements(
    db: AsyncSession, ctx: TenantContext, item_id: uuid.UUID, date_from: date, date_to: date,
    godown_id: uuid.UUID | None,
) -> list[StockMovementOut]:  # fmt: skip
    if date_from > date_to:
        raise ValidationFailedError("date_from must be on or before date_to")
    item = await repo.get(db, StockItem, ctx.org_id, item_id)
    if item is None:
        raise NotFoundError()
    rows = await repo.stock_movements(db, ctx.org_id, [item_id], date_to=date_to)
    val = value_stock(item.valuation_method, item.opening_qty, item.opening_rate, _movements(rows).get(item_id, []))
    names = await repo.godown_names(db, ctx.org_id)
    main = next(
        (g.id for g in await repo.list_all(db, Godown, ctx.org_id, Godown.name) if g.system_code == "MAIN"), None
    )
    gqty = item.opening_qty if godown_id is None or godown_id == main else ZERO
    out = []
    for step in val.steps:
        r = step.movement.ref
        vie = r[0]
        if godown_id is not None:
            if vie.godown_id != godown_id:
                continue
            gqty += vie.quantity if vie.movement_type == "INWARD" else -vie.quantity
        if r.voucher_date < date_from:
            continue
        bal_qty = gqty if godown_id is not None else step.balance_qty
        bal_val = q4(bal_qty * step.rate) if godown_id is not None else step.balance_value
        inward = vie.quantity if vie.movement_type == "INWARD" else ZERO
        outward = vie.quantity if vie.movement_type == "OUTWARD" else ZERO
        rate = q4(step.cost / step.qty) if step.qty else ZERO
        out.append(StockMovementOut(date=r.voucher_date, voucher_id=vie.voucher_id, voucher_number=r.voucher_number,
                                    voucher_type=r.vt_name, godown_name=names.get(vie.godown_id, ""),
                                    inward_qty=inward, outward_qty=outward, rate=rate, balance_qty=bal_qty,
                                    balance_value=bal_val))  # fmt: skip
    return out


def day_before(d: date) -> date:
    return d - timedelta(days=1)
