"""Accounts data access (queries only; flush, never commit). Every query filters ``org_id`` explicitly on top of RLS.

Report rule (plan §3.8): balances use only ``status='REGULAR'`` vouchers of accounting voucher types.
Stock uses REGULAR vouchers of every type except orders / memorandum / reversing journal / attendance.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.money import ZERO
from app.modules.accounts.ledger_math import Chart, GroupNode, LedgerNode, opening_signed
from app.modules.accounts.models import (
    AccountGroup,
    CostCentre,
    Godown,
    Ledger,
    StockGroup,
    StockItem,
    Voucher,
    VoucherEntry,
    VoucherInventoryEntry,
    VoucherType,
)

NON_STOCK_BASE_TYPES = ("SALES_ORDER", "PURCHASE_ORDER", "JOB_WORK_IN_ORDER", "JOB_WORK_OUT_ORDER", "MEMORANDUM",
                        "REVERSING_JOURNAL", "ATTENDANCE")  # fmt: skip


def books_filter() -> Any:
    return and_(Voucher.status == "REGULAR", VoucherType.is_accounting.is_(True))


def stock_filter() -> Any:
    return and_(Voucher.status == "REGULAR", VoucherType.base_type.not_in(NON_STOCK_BASE_TYPES))


async def add(db: AsyncSession, obj: object) -> None:
    db.add(obj)
    await db.flush()


# ---------------------------------------------------------------- chart
async def load_chart(db: AsyncSession, org_id: uuid.UUID) -> Chart:
    groups = (await db.execute(select(AccountGroup).where(AccountGroup.org_id == org_id))).scalars().all()
    ledgers = (await db.execute(select(Ledger).where(Ledger.org_id == org_id))).scalars().all()
    return Chart(
        groups={g.id: GroupNode(g.id, g.name, g.parent_group_id, g.nature, g.affects_gross_profit, g.system_code,
                                g.is_system_group) for g in groups},
        ledgers={lg.id: LedgerNode(lg.id, lg.name, lg.group_id, lg.system_code,
                                   opening_signed(lg.opening_balance, lg.opening_balance_type), lg.is_active,
                                   dict(lg.party_details or {}), lg.tax_config, lg.default_credit_days,
                                   lg.maintain_bill_by_bill) for lg in ledgers},
    )  # fmt: skip


async def ledger_totals(
    db: AsyncSession,
    org_id: uuid.UUID,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    ledger_ids: list[uuid.UUID] | None = None,
    cost_centre_ids: list[uuid.UUID] | None = None,
) -> dict[uuid.UUID, tuple[Decimal, Decimal]]:
    """(ΣDR, ΣCR) per ledger over REGULAR accounting vouchers in [date_from, date_to]."""
    dr = func.coalesce(func.sum(case((VoucherEntry.entry_type == "DR", VoucherEntry.amount), else_=0)), 0)
    cr = func.coalesce(func.sum(case((VoucherEntry.entry_type == "CR", VoucherEntry.amount), else_=0)), 0)
    stmt = (
        select(VoucherEntry.ledger_id, dr, cr)
        .join(Voucher, Voucher.id == VoucherEntry.voucher_id)
        .join(VoucherType, VoucherType.id == Voucher.voucher_type_id)
        .where(VoucherEntry.org_id == org_id, books_filter())
        .group_by(VoucherEntry.ledger_id)
    )
    if date_from:
        stmt = stmt.where(Voucher.voucher_date >= date_from)
    if date_to:
        stmt = stmt.where(Voucher.voucher_date <= date_to)
    if ledger_ids is not None:
        stmt = stmt.where(VoucherEntry.ledger_id.in_(ledger_ids))
    if cost_centre_ids is not None:
        stmt = stmt.where(VoucherEntry.cost_centre_id.in_(cost_centre_ids))
    return {lid: (Decimal(d), Decimal(c)) for lid, d, c in (await db.execute(stmt)).all()}


async def balances(db: AsyncSession, chart: Chart, org_id: uuid.UUID, as_of: date | None) -> dict[uuid.UUID, Decimal]:
    """Signed closing balance (opening + ΣDR - ΣCR) per ledger as of ``as_of`` (inclusive)."""
    totals = await ledger_totals(db, org_id, date_to=as_of)
    return {lid: lg.opening + totals.get(lid, (ZERO, ZERO))[0] - totals.get(lid, (ZERO, ZERO))[1]
            for lid, lg in chart.ledgers.items()}  # fmt: skip


async def monthly_ledger_totals(
    db: AsyncSession, org_id: uuid.UUID, ledger_ids: list[uuid.UUID], date_from: date, date_to: date,
    exclude_base_types: tuple[str, ...] = (),
) -> list[Any]:  # fmt: skip
    month = func.date_trunc("month", Voucher.voucher_date)
    stmt = (
        select(month.label("m"), VoucherEntry.entry_type, func.sum(VoucherEntry.amount))
        .join(Voucher, Voucher.id == VoucherEntry.voucher_id)
        .join(VoucherType, VoucherType.id == Voucher.voucher_type_id)
        .where(VoucherEntry.org_id == org_id, books_filter(), VoucherEntry.ledger_id.in_(ledger_ids),
               Voucher.voucher_date.between(date_from, date_to))
        .group_by(month, VoucherEntry.entry_type)
    )  # fmt: skip
    if exclude_base_types:
        stmt = stmt.where(VoucherType.base_type.not_in(exclude_base_types))
    return list((await db.execute(stmt)).all())


def entry_rows_stmt(org_id: uuid.UUID) -> Select[Any]:
    return (
        select(VoucherEntry, Voucher, VoucherType.name.label("vt_name"), VoucherType.base_type)
        .join(Voucher, Voucher.id == VoucherEntry.voucher_id)
        .join(VoucherType, VoucherType.id == Voucher.voucher_type_id)
        .where(VoucherEntry.org_id == org_id, books_filter())
    )


async def ledger_entries(
    db: AsyncSession, org_id: uuid.UUID, ledger_ids: list[uuid.UUID], date_from: date | None, date_to: date | None
) -> list[Any]:
    stmt = entry_rows_stmt(org_id).where(VoucherEntry.ledger_id.in_(ledger_ids))
    if date_from:
        stmt = stmt.where(Voucher.voucher_date >= date_from)
    if date_to:
        stmt = stmt.where(Voucher.voucher_date <= date_to)
    stmt = stmt.order_by(Voucher.voucher_date, Voucher.created_at, Voucher.voucher_number, VoucherEntry.id)
    return list((await db.execute(stmt)).all())


async def entries_of_vouchers(db: AsyncSession, voucher_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[VoucherEntry]]:
    out: dict[uuid.UUID, list[VoucherEntry]] = {v: [] for v in voucher_ids}
    if voucher_ids:
        rows = await db.execute(select(VoucherEntry).where(VoucherEntry.voucher_id.in_(voucher_ids))
                                .order_by(VoucherEntry.entry_type.desc(), VoucherEntry.id))  # fmt: skip
        for e in rows.scalars():
            out[e.voucher_id].append(e)
    return out


async def inventory_of_vouchers(
    db: AsyncSession, voucher_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[VoucherInventoryEntry]]:
    out: dict[uuid.UUID, list[VoucherInventoryEntry]] = {v: [] for v in voucher_ids}
    if voucher_ids:
        rows = await db.execute(select(VoucherInventoryEntry).where(VoucherInventoryEntry.voucher_id.in_(voucher_ids))
                                .order_by(VoucherInventoryEntry.id))  # fmt: skip
        for i in rows.scalars():
            out[i.voucher_id].append(i)
    return out


# ---------------------------------------------------------------- simple getters
async def get(db: AsyncSession, model: Any, org_id: uuid.UUID, obj_id: uuid.UUID | None) -> Any:
    if obj_id is None:
        return None
    return (await db.execute(select(model).where(model.id == obj_id, model.org_id == org_id))).scalar_one_or_none()


async def get_many(db: AsyncSession, model: Any, org_id: uuid.UUID, ids: list[uuid.UUID]) -> dict[uuid.UUID, Any]:
    if not ids:
        return {}
    rows = await db.execute(select(model).where(model.org_id == org_id, model.id.in_(set(ids))))
    return {r.id: r for r in rows.scalars()}


async def list_all(db: AsyncSession, model: Any, org_id: uuid.UUID, *order: Any) -> list[Any]:
    return list((await db.execute(select(model).where(model.org_id == org_id).order_by(*order))).scalars())


async def name_taken(
    db: AsyncSession, model: Any, org_id: uuid.UUID, name: str, exclude: uuid.UUID | None = None
) -> bool:
    stmt = select(model.id).where(model.org_id == org_id, func.lower(model.name) == name.lower())
    if exclude:
        stmt = stmt.where(model.id != exclude)
    return (await db.execute(stmt.limit(1))).first() is not None


async def page_scalars(db: AsyncSession, stmt: Select[Any], page: Any) -> tuple[list[Any], int]:
    total = (await db.execute(select(func.count()).select_from(stmt.order_by(None).subquery()))).scalar_one()
    rows = (await db.execute(stmt.limit(page.limit).offset(page.offset))).scalars().all()
    return list(rows), int(total)


async def exists(db: AsyncSession, stmt: Select[Any]) -> bool:
    return (await db.execute(stmt.limit(1))).first() is not None


async def voucher_type_for_update(db: AsyncSession, org_id: uuid.UUID, vt_id: uuid.UUID) -> VoucherType | None:
    stmt = select(VoucherType).where(VoucherType.id == vt_id, VoucherType.org_id == org_id).with_for_update()
    return (await db.execute(stmt)).scalar_one_or_none()


async def system_voucher_type(db: AsyncSession, org_id: uuid.UUID, base_type: str) -> VoucherType | None:
    stmt = (select(VoucherType).where(VoucherType.org_id == org_id, VoucherType.base_type == base_type)
            .order_by(VoucherType.is_system.desc(), VoucherType.name).limit(1))  # fmt: skip
    return (await db.execute(stmt)).scalar_one_or_none()


async def voucher_number_taken(db: AsyncSession, org_id: uuid.UUID, vt_id: uuid.UUID, number: str) -> bool:
    return await exists(db, select(Voucher.id).where(Voucher.org_id == org_id, Voucher.voucher_type_id == vt_id,
                                                     Voucher.voucher_number == number))  # fmt: skip


async def cost_centre_actuals(db: AsyncSession, org_id: uuid.UUID) -> dict[uuid.UUID, Decimal]:
    net = func.sum(case((VoucherEntry.entry_type == "DR", VoucherEntry.amount), else_=-VoucherEntry.amount))
    stmt = (
        select(VoucherEntry.cost_centre_id, net)
        .join(Voucher, Voucher.id == VoucherEntry.voucher_id)
        .join(VoucherType, VoucherType.id == Voucher.voucher_type_id)
        .where(VoucherEntry.org_id == org_id, VoucherEntry.cost_centre_id.is_not(None), books_filter())
        .group_by(VoucherEntry.cost_centre_id)
    )
    return {cid: Decimal(v) for cid, v in (await db.execute(stmt)).all()}


# ---------------------------------------------------------------- inventory
async def stock_movements(
    db: AsyncSession,
    org_id: uuid.UUID,
    item_ids: list[uuid.UUID] | None = None,
    *,
    date_to: date | None = None,
) -> list[Any]:
    """Chronological inventory rows (REGULAR stock-affecting vouchers) with voucher info."""
    stmt = (
        select(VoucherInventoryEntry, Voucher.voucher_date, Voucher.voucher_number, VoucherType.name.label("vt_name"),
               Voucher.created_at)
        .join(Voucher, Voucher.id == VoucherInventoryEntry.voucher_id)
        .join(VoucherType, VoucherType.id == Voucher.voucher_type_id)
        .where(VoucherInventoryEntry.org_id == org_id, stock_filter())
    )  # fmt: skip
    if item_ids is not None:
        stmt = stmt.where(VoucherInventoryEntry.stock_item_id.in_(item_ids))
    if date_to:
        stmt = stmt.where(Voucher.voucher_date <= date_to)
    stmt = stmt.order_by(Voucher.voucher_date, VoucherInventoryEntry.movement_type.asc(), Voucher.created_at,
                         VoucherInventoryEntry.id)  # INWARD before OUTWARD on the same day  # fmt: skip
    return list((await db.execute(stmt)).all())


async def items_with_groups(db: AsyncSession, org_id: uuid.UUID, ids: list[uuid.UUID] | None = None) -> list[Any]:
    stmt = (select(StockItem, StockGroup.name.label("group_name"))
            .outerjoin(StockGroup, StockGroup.id == StockItem.stock_group_id).where(StockItem.org_id == org_id)
            .order_by(StockItem.name))  # fmt: skip
    if ids is not None:
        stmt = stmt.where(StockItem.id.in_(ids))
    return list((await db.execute(stmt)).all())


async def godown_names(db: AsyncSession, org_id: uuid.UUID) -> dict[uuid.UUID, str]:
    return {g.id: g.name for g in await list_all(db, Godown, org_id, Godown.name)}


async def cost_centre_names(db: AsyncSession, org_id: uuid.UUID) -> dict[uuid.UUID, str]:
    return {c.id: c.name for c in await list_all(db, CostCentre, org_id, CostCentre.name)}
