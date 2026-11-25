"""Public API of the accounts module (binding signatures, plan §3.6).

Binding (plan §3.6): ``post_system_voucher``, ``create_cost_centre``, ``get_ledger_ids_by_code``,
``get_system_godown_ids``, ``get_stock_item``, ``list_vouchers_for_run``, ``link_voucher_to_run``, ``seed_org_accounts``.
Extra read helpers (S2): ``get_ledger`` / ``get_ledger_briefs`` (LedgerDTO incl. group + nature),
``ledger_balance`` (signed DR+), ``stock_valuation`` (qty/value/rate at a date), ``get_voucher``,
``cost_centre_for_run``, ``list_vouchers_full`` / ``get_voucher_full`` (+ ``update_voucher_gst_metadata``) used by
taxation. ``resource_names`` supports STOCK_ITEM, GODOWN and LEDGER.

All helpers are org-scoped (explicit ``org_id`` filter + RLS); unknown/cross-tenant ids raise ``NotFoundError``.
Postings go through the same validation as ``POST /accounts/vouchers`` (balance, active ledgers, period lock,
books bounds); the same ledger may appear on several entries (e.g. one DIRECT_WAGES line per cost centre).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import TenantContext
from app.core.errors import NotFoundError
from app.core.pagination import PageParams
from app.modules.accounts.models import CostCentre, Godown, Ledger, StockItem, Voucher, VoucherEntry, VoucherType
from app.modules.accounts.schemas import BomComponent, KpiOut, StockItemIn
from app.modules.accounts.seeding import seed_org_accounts


@dataclass(frozen=True, slots=True)
class SystemEntry:
    ledger_id: uuid.UUID
    entry_type: str  # DR | CR
    amount: Decimal
    cost_centre_id: uuid.UUID | None = None
    bill_allocations: list[dict[str, Any]] | None = None


@dataclass(frozen=True, slots=True)
class SystemInventory:
    stock_item_id: uuid.UUID
    godown_id: uuid.UUID
    movement_type: str  # INWARD | OUTWARD
    quantity: Decimal
    rate: Decimal
    amount: Decimal | None = None
    batch_number: str | None = None


@dataclass(frozen=True, slots=True)
class StockItemDTO:
    id: uuid.UUID
    name: str
    sku_code: str | None
    target_type: str
    uom_primary: str
    valuation_method: str
    hsn_sac_code: str | None
    gst_rate: Decimal
    opening_qty: Decimal
    opening_rate: Decimal
    custom_fields: dict[str, Any]
    bom_components: list[dict[str, Any]]
    diagram_storage_key: str | None
    stock_group_id: uuid.UUID | None


@dataclass(frozen=True, slots=True)
class VoucherDTO:
    id: uuid.UUID
    voucher_number: str
    voucher_date: date
    base_type: str
    voucher_type_name: str
    party_name: str | None
    total_amount: Decimal
    status: str
    narration: str | None
    linked_period_run_id: uuid.UUID | None
    linked_step_id: uuid.UUID | None
    created_at: datetime
    entries: list[dict[str, Any]] = field(default_factory=list)


async def get_ledger_ids_by_code(db: AsyncSession, ctx: TenantContext, codes: list[str]) -> dict[str, uuid.UUID]:
    rows = await db.execute(
        select(Ledger.system_code, Ledger.id).where(Ledger.org_id == ctx.org_id, Ledger.system_code.in_(codes))
    )
    return {code: lid for code, lid in rows.all()}


async def get_system_godown_ids(db: AsyncSession, ctx: TenantContext) -> dict[str, uuid.UUID]:
    """Keys MAIN, WIP, SCRAP, FG."""
    rows = await db.execute(
        select(Godown.system_code, Godown.id).where(Godown.org_id == ctx.org_id, Godown.system_code.is_not(None))
    )
    return {code: gid for code, gid in rows.all()}


async def resource_names(
    db: AsyncSession, ctx: TenantContext, resource_type: str, ids: list[uuid.UUID]
) -> dict[uuid.UUID, str]:
    """Names for ACL display/validation (STOCK_ITEM, GODOWN, LEDGER)."""
    model = {"STOCK_ITEM": StockItem, "GODOWN": Godown, "LEDGER": Ledger}.get(resource_type)
    if model is None or not ids:
        return {}
    rows = await db.execute(select(model.id, model.name).where(model.org_id == ctx.org_id, model.id.in_(ids)))
    return {i: n for i, n in rows.all()}


# ---------------------------------------------------------------- implemented by S2
async def post_system_voucher(
    db: AsyncSession,
    ctx: TenantContext,
    *,
    base_type: str,
    voucher_date: date,
    entries: list[SystemEntry],
    inventory: list[SystemInventory] | None = None,
    narration: str | None,
    linked_period_run_id: uuid.UUID | None = None,
    linked_step_id: uuid.UUID | None = None,
    status: str = "REGULAR",
) -> uuid.UUID:
    """Post a voucher of the (first, system-preferred) voucher type with ``base_type``. Raises the same domain
    errors as the API (DOUBLE_ENTRY_IMBALANCE, PERIOD_LOCKED, VALIDATION_ERROR). Zero-amount lines are dropped."""
    from app.modules.accounts.voucher_service import post_system

    return await post_system(db, ctx, base_type=base_type, voucher_date=voucher_date, entries=entries,
                             inventory=inventory or [], narration=narration, linked_period_run_id=linked_period_run_id,
                             linked_step_id=linked_step_id, status=status)  # fmt: skip


async def create_cost_centre(
    db: AsyncSession, ctx: TenantContext, *, name: str, linked_period_run_id: uuid.UUID | None
) -> uuid.UUID:
    """Idempotent per run: returns the existing cost centre linked to ``linked_period_run_id``; a clashing name gets
    a numeric suffix. Category "Operations Period Runs"."""
    from app.modules.accounts import service
    from app.modules.accounts.schemas import CostCentreIn

    if linked_period_run_id is not None:
        existing = await cost_centre_for_run(db, ctx, linked_period_run_id)
        if existing is not None:
            return existing
    base, n, candidate = name.strip()[:190] or "Period Run", 2, name.strip()[:190] or "Period Run"
    while (await db.execute(select(CostCentre.id).where(CostCentre.org_id == ctx.org_id,
                                                        func.lower(CostCentre.name) == candidate.lower()))).first():  # fmt: skip
        candidate, n = f"{base} ({n})", n + 1
    out = await service.create_cost_centre(db, ctx, CostCentreIn(category_name="Operations Period Runs", name=candidate),
                                           linked_period_run_id=linked_period_run_id)  # fmt: skip
    return out.id


async def cost_centre_for_run(db: AsyncSession, ctx: TenantContext, run_id: uuid.UUID) -> uuid.UUID | None:
    return (await db.execute(select(CostCentre.id).where(CostCentre.org_id == ctx.org_id,
                                                         CostCentre.linked_period_run_id == run_id).limit(1))).scalar()  # fmt: skip


def _item_dto(i: StockItem) -> StockItemDTO:
    return StockItemDTO(id=i.id, name=i.name, sku_code=i.sku_code, target_type=i.target_type, uom_primary=i.uom_primary,
                        valuation_method=i.valuation_method, hsn_sac_code=i.hsn_sac_code, gst_rate=i.gst_rate,
                        opening_qty=i.opening_qty, opening_rate=i.opening_rate, custom_fields=dict(i.custom_fields or {}),
                        bom_components=list(i.bom_components or []), diagram_storage_key=i.diagram_storage_key,
                        stock_group_id=i.stock_group_id)  # fmt: skip


async def get_stock_item(db: AsyncSession, ctx: TenantContext, item_id: uuid.UUID) -> StockItemDTO:
    item = (await db.execute(select(StockItem).where(StockItem.id == item_id, StockItem.org_id == ctx.org_id))).scalar()
    if item is None:
        raise NotFoundError()
    return _item_dto(item)


async def _voucher_dtos(db: AsyncSession, ctx: TenantContext, vouchers: list[Voucher]) -> list[VoucherDTO]:
    from app.modules.accounts import repository as repo

    vts = await repo.get_many(db, VoucherType, ctx.org_id, [v.voucher_type_id for v in vouchers])
    entries = await repo.entries_of_vouchers(db, [v.id for v in vouchers])
    lids = {e.ledger_id for es in entries.values() for e in es} | {
        v.party_ledger_id for v in vouchers if v.party_ledger_id
    }
    ledgers = await repo.get_many(db, Ledger, ctx.org_id, list(lids))
    return [VoucherDTO(id=v.id, voucher_number=v.voucher_number, voucher_date=v.voucher_date,
                       base_type=vts[v.voucher_type_id].base_type, voucher_type_name=vts[v.voucher_type_id].name,
                       party_name=ledgers[v.party_ledger_id].name if v.party_ledger_id in ledgers else None,
                       total_amount=v.total_amount, status=v.status, narration=v.narration,
                       linked_period_run_id=v.linked_period_run_id, linked_step_id=v.linked_step_id,
                       created_at=v.created_at,
                       entries=[{"id": e.id, "ledger_id": e.ledger_id, "ledger_name": ledgers[e.ledger_id].name,
                                 "ledger_system_code": ledgers[e.ledger_id].system_code, "entry_type": e.entry_type,
                                 "amount": e.amount, "cost_centre_id": e.cost_centre_id} for e in entries[v.id]])
            for v in vouchers]  # fmt: skip


async def get_voucher(db: AsyncSession, ctx: TenantContext, voucher_id: uuid.UUID) -> VoucherDTO:
    v = (await db.execute(select(Voucher).where(Voucher.id == voucher_id, Voucher.org_id == ctx.org_id))).scalar()
    if v is None:
        raise NotFoundError()
    return (await _voucher_dtos(db, ctx, [v]))[0]


async def list_vouchers_for_run(db: AsyncSession, ctx: TenantContext, run_id: uuid.UUID) -> list[VoucherDTO]:
    """Vouchers linked to the run (``linked_period_run_id``) or carrying an entry on the run's cost centre.
    All statuses (callers filter CANCELLED if needed); ordered by date."""
    cc_ids = select(CostCentre.id).where(CostCentre.org_id == ctx.org_id, CostCentre.linked_period_run_id == run_id)
    via_cc = select(VoucherEntry.voucher_id).where(
        VoucherEntry.org_id == ctx.org_id, VoucherEntry.cost_centre_id.in_(cc_ids)
    )
    rows = (await db.execute(select(Voucher).where(Voucher.org_id == ctx.org_id,
                                                   (Voucher.linked_period_run_id == run_id) | Voucher.id.in_(via_cc))
                             .order_by(Voucher.voucher_date, Voucher.created_at))).scalars().all()  # fmt: skip
    return await _voucher_dtos(db, ctx, list(rows))


async def link_voucher_to_run(
    db: AsyncSession,
    ctx: TenantContext,
    *,
    voucher_id: uuid.UUID,
    run_id: uuid.UUID | None,
    step_id: uuid.UUID | None = None,
) -> None:
    """Sets ``vouchers.linked_period_run_id`` / ``linked_step_id`` (audited); ``run_id=None`` unlinks.
    Linking a cancelled voucher -> INVALID_STATE."""
    from app.core.audit import write_audit
    from app.core.errors import InvalidStateError

    v = (await db.execute(select(Voucher).where(Voucher.id == voucher_id, Voucher.org_id == ctx.org_id))).scalar()
    if v is None:
        raise NotFoundError()
    if v.status == "CANCELLED" and run_id is not None:
        raise InvalidStateError("Cancelled vouchers cannot be linked")
    before = {"linked_period_run_id": v.linked_period_run_id, "linked_step_id": v.linked_step_id}
    v.linked_period_run_id, v.linked_step_id = run_id, step_id
    await db.flush()
    await write_audit(db, ctx, "ACCOUNTS", "UPDATE", "voucher", v.id, before=before,
                      after={"linked_period_run_id": run_id, "linked_step_id": step_id})  # fmt: skip


# ---------------------------------------------------------------- extra read helpers
@dataclass(frozen=True, slots=True)
class LedgerDTO:
    id: uuid.UUID
    name: str
    group_id: uuid.UUID
    group_name: str
    group_system_code: str | None
    primary_group_code: str | None
    nature: str
    system_code: str | None
    is_active: bool
    party_details: dict[str, Any]
    tax_config: dict[str, Any] | None
    opening_balance: Decimal
    opening_balance_type: str
    default_credit_days: int | None
    is_bank: bool
    is_party: bool


async def get_ledger_briefs(db: AsyncSession, ctx: TenantContext, ids: list[uuid.UUID] | None = None
                            ) -> dict[uuid.UUID, LedgerDTO]:  # fmt: skip
    from app.modules.accounts import repository as repo

    chart = await repo.load_chart(db, ctx.org_id)
    rows = await repo.get_many(db, Ledger, ctx.org_id, ids) if ids is not None else {k: None for k in chart.ledgers}
    banks = chart.subtree("BANK_ACCOUNTS", "BANK_OD")
    parties = chart.subtree("SUNDRY_DEBTORS", "SUNDRY_CREDITORS")
    out = {}
    for lid in rows:
        node = chart.ledgers[lid]
        g = chart.groups[node.group_id]
        lg = rows[lid]
        out[lid] = LedgerDTO(id=lid, name=node.name, group_id=g.id, group_name=g.name, group_system_code=g.system_code,
                             primary_group_code=chart.primary(g.id).system_code, nature=g.nature,
                             system_code=node.system_code, is_active=node.is_active, party_details=node.party_details,
                             tax_config=node.tax_config,
                             opening_balance=lg.opening_balance if lg else abs(node.opening),
                             opening_balance_type=lg.opening_balance_type if lg else ("DR" if node.opening >= 0 else "CR"),
                             default_credit_days=node.default_credit_days, is_bank=g.id in banks,
                             is_party=g.id in parties)  # fmt: skip
    return out


async def get_ledger(db: AsyncSession, ctx: TenantContext, ledger_id: uuid.UUID) -> LedgerDTO:
    found = await get_ledger_briefs(db, ctx, [ledger_id])
    if ledger_id not in found:
        raise NotFoundError()
    return found[ledger_id]


async def ledger_balance(
    db: AsyncSession, ctx: TenantContext, ledger_id: uuid.UUID, as_of: date | None = None
) -> Decimal:
    """Signed closing balance (DR positive) of REGULAR accounting vouchers up to ``as_of`` incl. opening."""
    from app.modules.accounts import repository as repo

    lg = await get_ledger(db, ctx, ledger_id)
    dr, cr = (await repo.ledger_totals(db, ctx.org_id, date_to=as_of, ledger_ids=[ledger_id])).get(
        ledger_id, (Decimal(0), Decimal(0)))  # fmt: skip
    opening = lg.opening_balance if lg.opening_balance_type == "DR" else -lg.opening_balance
    return opening + dr - cr


@dataclass(frozen=True, slots=True)
class StockValuationDTO:
    stock_item_id: uuid.UUID
    quantity: Decimal
    value: Decimal
    rate: Decimal
    method: str


async def stock_valuation(db: AsyncSession, ctx: TenantContext, item_id: uuid.UUID, as_of: date | None = None
                          ) -> StockValuationDTO:  # fmt: skip
    """Closing qty / value / running unit rate (the item's valuation method) — use the rate to cost consumption."""
    from app.modules.accounts.inventory_service import valuations

    item = (await db.execute(select(StockItem).where(StockItem.id == item_id, StockItem.org_id == ctx.org_id))).scalar()
    if item is None:
        raise NotFoundError()
    v = (await valuations(db, ctx.org_id, [item], as_of))[item.id]
    return StockValuationDTO(item.id, v.closing_qty, v.closing_value, v.rate, v.method)


@dataclass(frozen=True, slots=True)
class VoucherFullDTO:
    id: uuid.UUID
    voucher_number: str
    voucher_date: date
    voucher_type_name: str
    base_type: str
    status: str
    party_ledger_id: uuid.UUID | None
    party: LedgerDTO | None
    supplier_invoice_no: str | None
    supplier_invoice_date: date | None
    total_amount: Decimal
    narration: str | None
    gst_metadata: dict[str, Any]
    entries: list[
        dict[str, Any]
    ]  # ledger_id, ledger_name, system_code, nature, tax_config, is_party, entry_type, amount
    inventory: list[dict[str, Any]]  # stock_item_id, name, hsn, uom, quantity, rate, amount, gst_rate, movement_type


async def list_vouchers_full(
    db: AsyncSession, ctx: TenantContext, *, date_from: date | None = None, date_to: date | None = None,
    base_types: list[str] | None = None, party_ledger_id: uuid.UUID | None = None,
    statuses: tuple[str, ...] = ("REGULAR",), voucher_ids: list[uuid.UUID] | None = None,
) -> list[VoucherFullDTO]:  # fmt: skip
    from app.modules.accounts import repository as repo

    stmt = (select(Voucher, VoucherType).join(VoucherType, VoucherType.id == Voucher.voucher_type_id)
            .where(Voucher.org_id == ctx.org_id).order_by(Voucher.voucher_date, Voucher.created_at))  # fmt: skip
    if statuses:
        stmt = stmt.where(Voucher.status.in_(statuses))
    if date_from:
        stmt = stmt.where(Voucher.voucher_date >= date_from)
    if date_to:
        stmt = stmt.where(Voucher.voucher_date <= date_to)
    if base_types:
        stmt = stmt.where(VoucherType.base_type.in_(base_types))
    if party_ledger_id:
        stmt = stmt.where(Voucher.party_ledger_id == party_ledger_id)
    if voucher_ids is not None:
        stmt = stmt.where(Voucher.id.in_(voucher_ids))
    rows = list((await db.execute(stmt)).all())
    vids = [v.id for v, _ in rows]
    entries = await repo.entries_of_vouchers(db, vids)
    inv = await repo.inventory_of_vouchers(db, vids)
    briefs = await get_ledger_briefs(db, ctx)
    items = await repo.get_many(db, StockItem, ctx.org_id, list({i.stock_item_id for es in inv.values() for i in es}))
    out = []
    for v, vt in rows:
        out.append(VoucherFullDTO(
            id=v.id, voucher_number=v.voucher_number, voucher_date=v.voucher_date, voucher_type_name=vt.name,
            base_type=vt.base_type, status=v.status, party_ledger_id=v.party_ledger_id,
            party=briefs.get(v.party_ledger_id) if v.party_ledger_id else None,
            supplier_invoice_no=v.supplier_invoice_no, supplier_invoice_date=v.supplier_invoice_date,
            total_amount=v.total_amount, narration=v.narration, gst_metadata=dict(v.gst_metadata or {}),
            entries=[{"id": e.id, "ledger_id": e.ledger_id, "ledger_name": briefs[e.ledger_id].name,
                      "system_code": briefs[e.ledger_id].system_code, "nature": briefs[e.ledger_id].nature,
                      "tax_config": briefs[e.ledger_id].tax_config, "is_party": briefs[e.ledger_id].is_party,
                      "entry_type": e.entry_type, "amount": e.amount}
                     for e in entries[v.id]],
            inventory=[{"stock_item_id": i.stock_item_id, "name": items[i.stock_item_id].name,
                        "hsn": items[i.stock_item_id].hsn_sac_code, "uom": items[i.stock_item_id].uom_primary,
                        "quantity": i.quantity, "rate": i.rate, "amount": i.amount, "gst_rate": i.gst_rate,
                        "movement_type": i.movement_type} for i in inv[v.id]],
        ))  # fmt: skip
    return out


async def get_voucher_full(db: AsyncSession, ctx: TenantContext, voucher_id: uuid.UUID) -> VoucherFullDTO:
    found = await list_vouchers_full(db, ctx, statuses=(), voucher_ids=[voucher_id])
    if not found:
        raise NotFoundError()
    return found[0]


async def update_voucher_gst_metadata(db: AsyncSession, ctx: TenantContext, voucher_id: uuid.UUID,
                                      patch: dict[str, Any]) -> None:  # fmt: skip
    """Shallow-merge ``patch`` into ``vouchers.gst_metadata`` (e-invoice / e-way bill results)."""
    from app.core.audit import to_jsonable

    v = (await db.execute(select(Voucher).where(Voucher.id == voucher_id, Voucher.org_id == ctx.org_id))).scalar()
    if v is None:
        raise NotFoundError()
    v.gst_metadata = {**(v.gst_metadata or {}), **to_jsonable(patch)}
    await db.flush()


# ---------------------------------------------------------------- stock-item facade (operations /items)
async def list_stock_items_out(
    db: AsyncSession, ctx: TenantContext, *, q: str | None, target_type: str | None, acl: Any, limit: int, offset: int
) -> tuple[list[dict[str, Any]], int]:
    """Contract ``StockItemOut`` dicts filtered by the caller's ``AclFilter`` (operations authorises)."""
    from sqlalchemy import or_

    from app.modules.accounts import repository as repo
    from app.modules.accounts.service import item_outs

    stmt = select(StockItem).where(StockItem.org_id == ctx.org_id, acl.clause(StockItem.id)).order_by(StockItem.name)
    if q:
        stmt = stmt.where(or_(StockItem.name.ilike(f"%{q.strip()}%"), StockItem.sku_code.ilike(f"%{q.strip()}%")))
    if target_type:
        stmt = stmt.where(StockItem.target_type == target_type)
    rows, total = await repo.page_scalars(db, stmt, PageParams(limit, offset))
    return [o.model_dump() for o in await item_outs(db, ctx, rows)], total


async def _item_row(db: AsyncSession, ctx: TenantContext, item_id: uuid.UUID) -> StockItem:
    item = (await db.execute(select(StockItem).where(StockItem.id == item_id, StockItem.org_id == ctx.org_id))).scalar()
    if item is None:
        raise NotFoundError()
    return item


async def get_stock_item_out(db: AsyncSession, ctx: TenantContext, item_id: uuid.UUID) -> dict[str, Any]:
    from app.modules.accounts.service import item_outs

    return (await item_outs(db, ctx, [await _item_row(db, ctx, item_id)]))[0].model_dump()


async def create_stock_item(db: AsyncSession, ctx: TenantContext, body: StockItemIn) -> dict[str, Any]:
    """Same validation + audit as ``POST /accounts/stock-items``."""
    from app.modules.accounts import service

    return (await service.create_stock_item(db, ctx, body)).model_dump()


async def update_stock_item(
    db: AsyncSession, ctx: TenantContext, item_id: uuid.UUID, body: StockItemIn
) -> dict[str, Any]:
    """Same validation + audit as ``PATCH /accounts/stock-items/{id}`` (record ACL is the caller's job)."""
    from app.modules.accounts import service

    return (await service.apply_item_update(db, ctx, await _item_row(db, ctx, item_id), body)).model_dump()


__all__ = [
    "BomComponent",
    "KpiOut",
    "LedgerDTO",
    "StockItemIn",
    "create_stock_item",
    "get_stock_item_out",
    "list_stock_items_out",
    "update_stock_item",
    "StockItemDTO",
    "StockValuationDTO",
    "VoucherFullDTO",
    "cost_centre_for_run",
    "get_ledger",
    "get_ledger_briefs",
    "get_voucher",
    "get_voucher_full",
    "ledger_balance",
    "list_vouchers_full",
    "stock_valuation",
    "update_voucher_gst_metadata",
    "SystemEntry",
    "SystemInventory",
    "VoucherDTO",
    "create_cost_centre",
    "get_ledger_ids_by_code",
    "get_stock_item",
    "get_system_godown_ids",
    "link_voucher_to_run",
    "list_vouchers_for_run",
    "post_system_voucher",
    "resource_names",
    "seed_org_accounts",
]
