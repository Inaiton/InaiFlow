"""Accounts masters: groups, ledgers (+ statement, outstanding bills), cost centres, voucher types, currencies,
godowns, stock groups, stock items, accounts settings. Services never commit; every mutation is audited."""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.storage import DOCUMENT_MIME_ALLOWLIST, build_org_key, get_storage, validate_upload
from app.core.audit import write_audit
from app.core.context import TenantContext
from app.core.deps import acl_list_filter, assert_resource_access
from app.core.errors import (
    AlreadyExistsError,
    ConflictError,
    LedgerInUseError,
    NotFoundError,
    SystemRecordError,
    ValidationFailedError,
)
from app.core.money import ZERO
from app.core.pagination import Page, PageParams
from app.core.schemas import UploadTicket
from app.modules.accounts import common
from app.modules.accounts import repository as repo
from app.modules.accounts.inventory_service import valuations
from app.modules.accounts.ledger_math import BillEntry, outstanding_bills, signed, split
from app.modules.accounts.models import (
    AccountGroup,
    ChequeBook,
    CostCentre,
    Currency,
    ExchangeRate,
    Godown,
    Ledger,
    StockGroup,
    StockItem,
    Voucher,
    VoucherEntry,
    VoucherInventoryEntry,
    VoucherType,
)
from app.modules.accounts.schemas import (
    AccountsSettings,
    CostCentreIn,
    CostCentreOut,
    CurrencyIn,
    CurrencyOut,
    ExchangeRateIn,
    GodownIn,
    GodownOut,
    GroupIn,
    GroupOut,
    GroupUpdateIn,
    LedgerIn,
    LedgerOut,
    LedgerStatementLine,
    LedgerStatementOut,
    OutstandingBillOut,
    StockGroupIn,
    StockGroupOut,
    StockItemIn,
    StockItemOut,
    StockItemUploadIn,
    VoucherTypeIn,
    VoucherTypeOut,
    VoucherTypeUpdateIn,
)
from app.modules.organization import interface as organization
from app.seeds.voucher_types import VOUCHER_TYPES

M = "ACCOUNTS"
BASE_TYPES = {vt["base_type"]: vt["is_accounting"] for vt in VOUCHER_TYPES}


async def _audit(db: AsyncSession, ctx: TenantContext, action: str, entity: str, eid: uuid.UUID,
                 before: Any = None, after: Any = None, reason: str | None = None) -> None:  # fmt: skip
    await write_audit(db, ctx, M, action, entity, eid, before=before, after=after, reason=reason,
                      changed_only=before is not None and after is not None)  # fmt: skip


async def _must(db: AsyncSession, model: Any, ctx: TenantContext, obj_id: uuid.UUID) -> Any:
    obj = await repo.get(db, model, ctx.org_id, obj_id)
    if obj is None:
        raise NotFoundError()
    return obj


# ================================================================= groups
def _group_out(g: AccountGroup) -> GroupOut:
    return GroupOut.model_validate(g)


async def list_groups(db: AsyncSession, ctx: TenantContext) -> list[GroupOut]:
    return [_group_out(g) for g in await repo.list_all(db, AccountGroup, ctx.org_id, AccountGroup.name)]


async def create_group(db: AsyncSession, ctx: TenantContext, body: GroupIn) -> GroupOut:
    parent = await _must(db, AccountGroup, ctx, body.parent_group_id)
    if await repo.name_taken(db, AccountGroup, ctx.org_id, body.name):
        raise AlreadyExistsError("A group with this name already exists")
    g = AccountGroup(org_id=ctx.org_id, name=body.name, parent_group_id=parent.id, nature=parent.nature,
                     affects_gross_profit=parent.affects_gross_profit, is_system_group=False)  # fmt: skip
    await repo.add(db, g)
    await _audit(db, ctx, "CREATE", "account_group", g.id, after=g.to_dict())
    return _group_out(g)


async def update_group(db: AsyncSession, ctx: TenantContext, group_id: uuid.UUID, body: GroupUpdateIn) -> GroupOut:
    g = await _must(db, AccountGroup, ctx, group_id)
    if g.is_system_group:
        raise SystemRecordError("Predefined groups cannot be changed")
    before = g.to_dict()
    if body.name is not None and body.name != g.name:
        if await repo.name_taken(db, AccountGroup, ctx.org_id, body.name, exclude=g.id):
            raise AlreadyExistsError("A group with this name already exists")
        g.name = body.name
    if body.parent_group_id is not None and body.parent_group_id != g.parent_group_id:
        parent = await _must(db, AccountGroup, ctx, body.parent_group_id)
        chart = await repo.load_chart(db, ctx.org_id)
        if g.id in chart.ancestors(parent.id):
            raise ValidationFailedError("A group cannot be moved under itself")
        g.parent_group_id, g.nature, g.affects_gross_profit = parent.id, parent.nature, parent.affects_gross_profit
        for gid in chart.subtree(g.id) - {g.id}:
            child = await repo.get(db, AccountGroup, ctx.org_id, gid)
            child.nature, child.affects_gross_profit = parent.nature, parent.affects_gross_profit
    await db.flush()
    await _audit(db, ctx, "UPDATE", "account_group", g.id, before, g.to_dict())
    return _group_out(g)


async def delete_group(db: AsyncSession, ctx: TenantContext, group_id: uuid.UUID) -> None:
    g = await _must(db, AccountGroup, ctx, group_id)
    if g.is_system_group:
        raise SystemRecordError("Predefined groups cannot be deleted")
    if await repo.exists(db, select(Ledger.id).where(Ledger.org_id == ctx.org_id, Ledger.group_id == g.id)) or \
            await repo.exists(db, select(AccountGroup.id).where(AccountGroup.parent_group_id == g.id)):  # fmt: skip
        raise ConflictError("The group has ledgers or sub-groups")
    before = g.to_dict()
    await db.delete(g)
    await db.flush()
    await _audit(db, ctx, "DELETE", "account_group", group_id, before=before)


# ================================================================= ledgers
async def _ledger_outs(db: AsyncSession, ctx: TenantContext, ledgers: list[Ledger]) -> list[LedgerOut]:
    chart = await repo.load_chart(db, ctx.org_id)
    totals = await repo.ledger_totals(db, ctx.org_id, ledger_ids=[lg.id for lg in ledgers])
    out = []
    for lg in ledgers:
        dr, cr = totals.get(lg.id, (ZERO, ZERO))
        out.append(common.ledger_out(lg, chart, chart.ledgers[lg.id].opening + dr - cr))
    return out


async def get_ledger(db: AsyncSession, ctx: TenantContext, ledger_id: uuid.UUID) -> LedgerOut:
    return (await _ledger_outs(db, ctx, [await _must(db, Ledger, ctx, ledger_id)]))[0]


async def list_ledgers(
    db: AsyncSession, ctx: TenantContext, page: PageParams, *, q: str | None, group_id: uuid.UUID | None,
    nature: str | None, party_only: bool, bank_only: bool, include_inactive: bool,
) -> Page[LedgerOut]:  # fmt: skip
    chart = await repo.load_chart(db, ctx.org_id)
    stmt = select(Ledger).where(Ledger.org_id == ctx.org_id).order_by(Ledger.name)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Ledger.name.ilike(like), Ledger.alias.ilike(like)))
    if group_id:
        stmt = stmt.where(Ledger.group_id.in_(chart.subtree(group_id)))
    if nature:
        stmt = stmt.where(Ledger.group_id.in_([g.id for g in chart.groups.values() if g.nature == nature]))
    if party_only:
        stmt = stmt.where(Ledger.group_id.in_(chart.subtree("SUNDRY_DEBTORS", "SUNDRY_CREDITORS")))
    if bank_only:
        stmt = stmt.where(Ledger.group_id.in_(chart.subtree("BANK_ACCOUNTS", "BANK_OD")))
    if not include_inactive:
        stmt = stmt.where(Ledger.is_active.is_(True))
    rows, total = await repo.page_scalars(db, stmt, page)
    return Page[LedgerOut](items=await _ledger_outs(db, ctx, rows), total=total, limit=page.limit, offset=page.offset)


def _json(model: Any) -> Any:
    return model.model_dump(mode="json", exclude_none=False) if model is not None else None


async def create_ledger(db: AsyncSession, ctx: TenantContext, body: LedgerIn) -> LedgerOut:
    await _must(db, AccountGroup, ctx, body.group_id)
    if await repo.name_taken(db, Ledger, ctx.org_id, body.name):
        raise AlreadyExistsError("A ledger with this name already exists")
    org = await common.org_brief(db, ctx)
    lg = Ledger(org_id=ctx.org_id, group_id=body.group_id, name=body.name, alias=body.alias,
                currency_code=(body.currency_code or org.base_currency_code).upper(),
                opening_balance=body.opening_balance, opening_balance_type=body.opening_balance_type,
                maintain_bill_by_bill=body.maintain_bill_by_bill, default_credit_days=body.default_credit_days,
                credit_limit=body.credit_limit, party_details=_json(body.party_details),
                tax_config=_json(body.tax_config), interest_config=_json(body.interest_config),
                is_active=body.is_active)  # fmt: skip
    await repo.add(db, lg)
    await db.refresh(lg)
    await _audit(db, ctx, "CREATE", "ledger", lg.id, after=lg.to_dict())
    return (await _ledger_outs(db, ctx, [lg]))[0]


async def update_ledger(db: AsyncSession, ctx: TenantContext, ledger_id: uuid.UUID, body: LedgerIn) -> LedgerOut:
    lg = await _must(db, Ledger, ctx, ledger_id)
    before = lg.to_dict()
    fields = body.model_fields_set
    if lg.system_code and (("group_id" in fields and body.group_id != lg.group_id)
                           or ("is_active" in fields and not body.is_active)):  # fmt: skip
        raise SystemRecordError("System ledgers cannot be moved or deactivated")
    if "group_id" in fields:
        await _must(db, AccountGroup, ctx, body.group_id)
        lg.group_id = body.group_id
    if "name" in fields and body.name != lg.name:
        if await repo.name_taken(db, Ledger, ctx.org_id, body.name, exclude=lg.id):
            raise AlreadyExistsError("A ledger with this name already exists")
        lg.name = body.name
    for f in ("alias", "opening_balance", "opening_balance_type", "maintain_bill_by_bill", "default_credit_days",
              "credit_limit", "is_active"):  # fmt: skip
        if f in fields:
            setattr(lg, f, getattr(body, f))
    if "currency_code" in fields and body.currency_code:
        lg.currency_code = body.currency_code.upper()
    for f in ("party_details", "tax_config", "interest_config"):
        if f in fields:
            setattr(lg, f, _json(getattr(body, f)))
    await db.flush()
    await _audit(db, ctx, "UPDATE", "ledger", lg.id, before, lg.to_dict())
    return (await _ledger_outs(db, ctx, [lg]))[0]


async def delete_ledger(db: AsyncSession, ctx: TenantContext, ledger_id: uuid.UUID) -> None:
    lg = await _must(db, Ledger, ctx, ledger_id)
    if lg.system_code:
        raise SystemRecordError("System ledgers cannot be deleted")
    used = await repo.exists(db, select(VoucherEntry.id).where(VoucherEntry.org_id == ctx.org_id,
                                                               VoucherEntry.ledger_id == lg.id))  # fmt: skip
    used = used or await repo.exists(db, select(Voucher.id).where(Voucher.org_id == ctx.org_id,
                                                                  Voucher.party_ledger_id == lg.id))  # fmt: skip
    used = used or await repo.exists(db, select(ChequeBook.id).where(ChequeBook.bank_ledger_id == lg.id))
    if used:
        raise LedgerInUseError()
    before = lg.to_dict()
    await db.delete(lg)
    await db.flush()
    await _audit(db, ctx, "DELETE", "ledger", ledger_id, before=before)


def _particulars(entries: list[VoucherEntry], own_ledger: uuid.UUID, own_side: str, names: dict) -> str:
    other = [e for e in entries if e.ledger_id != own_ledger and e.entry_type != own_side] or \
            [e for e in entries if e.ledger_id != own_ledger]  # fmt: skip
    if not other:
        return names.get(own_ledger, "")
    first = names.get(max(other, key=lambda e: e.amount).ledger_id, "")  # main counter-ledger = largest amount
    return first if len({e.ledger_id for e in other}) == 1 else f"{first} (as per details)"


async def ledger_statement(
    db: AsyncSession, ctx: TenantContext, ledger_id: uuid.UUID, date_from: date, date_to: date
) -> LedgerStatementOut:
    if date_from > date_to:
        raise ValidationFailedError("date_from must be on or before date_to")
    lg = await _must(db, Ledger, ctx, ledger_id)
    chart = await repo.load_chart(db, ctx.org_id)
    before = await repo.ledger_totals(db, ctx.org_id, date_to=date_from - timedelta(days=1), ledger_ids=[lg.id])
    dr0, cr0 = before.get(lg.id, (ZERO, ZERO))
    running = opening = chart.ledgers[lg.id].opening + dr0 - cr0
    rows = await repo.ledger_entries(db, ctx.org_id, [lg.id], date_from, date_to)
    all_entries = await repo.entries_of_vouchers(db, list({r[1].id for r in rows}))
    names = {i: n.name for i, n in chart.ledgers.items()}
    lines, tdr, tcr = [], ZERO, ZERO
    for e, v, vt_name, _bt in rows:
        running += signed(e.entry_type, e.amount)
        debit = e.amount if e.entry_type == "DR" else ZERO
        credit = e.amount if e.entry_type == "CR" else ZERO
        tdr, tcr = tdr + debit, tcr + credit
        rb, rt = split(running)
        lines.append(LedgerStatementLine(date=v.voucher_date, voucher_id=v.id, voucher_number=v.voucher_number,
                                         voucher_type=vt_name,
                                         particulars=_particulars(all_entries[v.id], lg.id, e.entry_type, names),
                                         narration=v.narration, debit=debit, credit=credit, running_balance=rb,
                                         running_type=rt))  # fmt: skip
    ob, ot = split(opening)
    cb, ct = split(running)
    led = (await _ledger_outs(db, ctx, [lg]))[0]
    return LedgerStatementOut(ledger=led, date_from=date_from, date_to=date_to, opening_balance=ob, opening_type=ot,
                              lines=lines, total_debit=tdr, total_credit=tcr, closing_balance=cb,
                              closing_type=ct)  # fmt: skip


async def compute_bills(db: AsyncSession, ctx: TenantContext, ledger_ids: list[uuid.UUID], as_of: date,
                        chart: Any = None) -> dict[uuid.UUID, list]:  # fmt: skip
    """Outstanding bills per ledger as of ``as_of`` (pure FIFO/bill-wise logic in ``ledger_math``)."""
    chart = chart or await repo.load_chart(db, ctx.org_id)
    org = await common.org_brief(db, ctx)
    rows = await repo.ledger_entries(db, ctx.org_id, ledger_ids, None, as_of)
    per: dict[uuid.UUID, list[BillEntry]] = {lid: [] for lid in ledger_ids}
    for e, v, _vt, _bt in rows:
        per[e.ledger_id].append(BillEntry(v.voucher_date, v.voucher_number, e.entry_type, e.amount,
                                          list(e.bill_allocations or [])))  # fmt: skip
    out = {}
    for lid in ledger_ids:
        node = chart.ledgers[lid]
        natural = "DR" if chart.nature(lid) in ("ASSETS", "EXPENSES") else "CR"
        out[lid] = outstanding_bills(natural_side=natural, opening=node.opening, opening_date=org.books_beginning_from,
                                     credit_days=node.default_credit_days, entries=per[lid])  # fmt: skip
    return out


async def ledger_bills(db: AsyncSession, ctx: TenantContext, ledger_id: uuid.UUID, as_of: date | None
                       ) -> list[OutstandingBillOut]:  # fmt: skip
    lg = await _must(db, Ledger, ctx, ledger_id)
    as_of = as_of or date.today()
    bills = (await compute_bills(db, ctx, [lg.id], as_of))[lg.id]
    out = []
    for b in bills:
        pending, kind = split(b.pending)
        overdue = max(0, (as_of - (b.due_date or b.bill_date)).days)
        out.append(OutstandingBillOut(ref_name=b.ref_name, bill_date=b.bill_date, due_date=b.due_date,
                                      amount=b.amount, pending=pending, pending_type=kind,
                                      overdue_days=overdue))  # fmt: skip
    return out


# ================================================================= cost centres
async def list_cost_centres(db: AsyncSession, ctx: TenantContext) -> list[CostCentreOut]:
    actuals = await repo.cost_centre_actuals(db, ctx.org_id)
    return [_cc_out(c, actuals) for c in await repo.list_all(db, CostCentre, ctx.org_id, CostCentre.name)]


def _cc_out(c: CostCentre, actuals: dict) -> CostCentreOut:
    return CostCentreOut(id=c.id, category_name=c.category_name, name=c.name, parent_id=c.parent_id,
                         linked_period_run_id=c.linked_period_run_id, budget_amount=c.budget_amount,
                         actual_amount=actuals.get(c.id, ZERO))  # fmt: skip


async def create_cost_centre(db: AsyncSession, ctx: TenantContext, body: CostCentreIn,
                             linked_period_run_id: uuid.UUID | None = None) -> CostCentreOut:  # fmt: skip
    if body.parent_id:
        await _must(db, CostCentre, ctx, body.parent_id)
    if await repo.name_taken(db, CostCentre, ctx.org_id, body.name):
        raise AlreadyExistsError("A cost centre with this name already exists")
    c = CostCentre(org_id=ctx.org_id, category_name=body.category_name or "Primary Cost Category", name=body.name,
                   parent_id=body.parent_id, budget_amount=body.budget_amount,
                   linked_period_run_id=linked_period_run_id)  # fmt: skip
    await repo.add(db, c)
    await _audit(db, ctx, "CREATE", "cost_centre", c.id, after=c.to_dict())
    return _cc_out(c, {})


async def update_cost_centre(db: AsyncSession, ctx: TenantContext, cc_id: uuid.UUID, body: CostCentreIn
                             ) -> CostCentreOut:  # fmt: skip
    c = await _must(db, CostCentre, ctx, cc_id)
    before = c.to_dict()
    if body.name != c.name and await repo.name_taken(db, CostCentre, ctx.org_id, body.name, exclude=c.id):
        raise AlreadyExistsError("A cost centre with this name already exists")
    if body.parent_id == c.id:
        raise ValidationFailedError("A cost centre cannot be its own parent")
    if body.parent_id:
        await _must(db, CostCentre, ctx, body.parent_id)
    c.name, c.parent_id = body.name, body.parent_id
    if "category_name" in body.model_fields_set and body.category_name:
        c.category_name = body.category_name
    if "budget_amount" in body.model_fields_set:
        c.budget_amount = body.budget_amount
    await db.flush()
    await _audit(db, ctx, "UPDATE", "cost_centre", c.id, before, c.to_dict())
    return _cc_out(c, await repo.cost_centre_actuals(db, ctx.org_id))


async def delete_cost_centre(db: AsyncSession, ctx: TenantContext, cc_id: uuid.UUID) -> None:
    c = await _must(db, CostCentre, ctx, cc_id)
    if c.linked_period_run_id:
        raise SystemRecordError("Cost centres linked to a period run cannot be deleted")
    if await repo.exists(db, select(VoucherEntry.id).where(VoucherEntry.org_id == ctx.org_id,
                                                           VoucherEntry.cost_centre_id == c.id)) or \
            await repo.exists(db, select(CostCentre.id).where(CostCentre.parent_id == c.id)):  # fmt: skip
        raise ConflictError("The cost centre is in use")
    before = c.to_dict()
    await db.delete(c)
    await db.flush()
    await _audit(db, ctx, "DELETE", "cost_centre", cc_id, before=before)


# ================================================================= voucher types
def _vt_out(v: VoucherType) -> VoucherTypeOut:
    return VoucherTypeOut(id=v.id, name=v.name, base_type=v.base_type, is_accounting=v.is_accounting,
                          is_system=v.is_system, shortcut=v.shortcut, numbering_method=v.numbering_method,
                          prefix=v.prefix or "", suffix=v.suffix or "", zero_padding=v.zero_padding,
                          next_number=v.next_number)  # fmt: skip


async def list_voucher_types(db: AsyncSession, ctx: TenantContext) -> list[VoucherTypeOut]:
    return [_vt_out(v) for v in await repo.list_all(db, VoucherType, ctx.org_id, VoucherType.name)]


def _numbering(method: str | None) -> str:
    method = (method or "AUTOMATIC").upper()
    if method not in ("AUTOMATIC", "AUTOMATIC_MANUAL_OVERRIDE"):
        raise ValidationFailedError("numbering_method must be AUTOMATIC (numbers are always allocated by the server)")
    return method


async def create_voucher_type(db: AsyncSession, ctx: TenantContext, body: VoucherTypeIn) -> VoucherTypeOut:
    base = body.base_type.upper()
    if base not in BASE_TYPES:
        raise ValidationFailedError(f"Unknown base_type {body.base_type}", details={"allowed": sorted(BASE_TYPES)})
    if await repo.name_taken(db, VoucherType, ctx.org_id, body.name):
        raise AlreadyExistsError("A voucher type with this name already exists")
    v = VoucherType(org_id=ctx.org_id, name=body.name, base_type=base, is_accounting=BASE_TYPES[base], is_system=False,
                    numbering_method=_numbering(body.numbering_method), prefix=body.prefix, suffix=body.suffix,
                    zero_padding=body.zero_padding, next_number=body.next_number)  # fmt: skip
    await repo.add(db, v)
    await _audit(db, ctx, "CREATE", "voucher_type", v.id, after=v.to_dict())
    return _vt_out(v)


async def update_voucher_type(db: AsyncSession, ctx: TenantContext, vt_id: uuid.UUID, body: VoucherTypeUpdateIn
                              ) -> VoucherTypeOut:  # fmt: skip
    v = await repo.voucher_type_for_update(db, ctx.org_id, vt_id)
    if v is None:
        raise NotFoundError()
    before = v.to_dict()
    if body.name is not None and body.name != v.name:
        if v.is_system:
            raise SystemRecordError("Predefined voucher types cannot be renamed")
        if await repo.name_taken(db, VoucherType, ctx.org_id, body.name, exclude=v.id):
            raise AlreadyExistsError("A voucher type with this name already exists")
        v.name = body.name
    if body.numbering_method is not None:
        v.numbering_method = _numbering(body.numbering_method)
    for f in ("prefix", "suffix", "zero_padding", "next_number"):
        if getattr(body, f) is not None:
            setattr(v, f, getattr(body, f))
    await db.flush()
    await _audit(db, ctx, "UPDATE", "voucher_type", v.id, before, v.to_dict())
    return _vt_out(v)


# ================================================================= currencies
async def _currency_out(db: AsyncSession, c: Currency) -> CurrencyOut:
    rate = (await db.execute(select(ExchangeRate).where(ExchangeRate.org_id == c.org_id,
                                                        ExchangeRate.currency_code == c.code)
                             .order_by(ExchangeRate.rate_date.desc()).limit(1))).scalar_one_or_none()  # fmt: skip
    return CurrencyOut(id=c.id, code=c.code, symbol=c.symbol, name=c.name, decimal_places=c.decimal_places,
                       latest_rate=rate.rate_to_base if rate else None,
                       latest_rate_date=rate.rate_date if rate else None)  # fmt: skip


async def list_currencies(db: AsyncSession, ctx: TenantContext) -> list[CurrencyOut]:
    return [await _currency_out(db, c) for c in await repo.list_all(db, Currency, ctx.org_id, Currency.code)]


async def create_currency(db: AsyncSession, ctx: TenantContext, body: CurrencyIn) -> CurrencyOut:
    code = body.code.upper()
    if await repo.exists(db, select(Currency.id).where(Currency.org_id == ctx.org_id, Currency.code == code)):
        raise AlreadyExistsError("This currency already exists")
    c = Currency(org_id=ctx.org_id, code=code, symbol=body.symbol, name=body.name, decimal_places=body.decimal_places)
    await repo.add(db, c)
    await _audit(db, ctx, "CREATE", "currency", c.id, after=c.to_dict())
    return await _currency_out(db, c)


async def add_exchange_rate(db: AsyncSession, ctx: TenantContext, currency_id: uuid.UUID, body: ExchangeRateIn
                            ) -> CurrencyOut:  # fmt: skip
    c = await _must(db, Currency, ctx, currency_id)
    org = await common.org_brief(db, ctx)
    if c.code == org.base_currency_code:
        raise ValidationFailedError("The base currency has no exchange rate")
    row = (await db.execute(select(ExchangeRate).where(ExchangeRate.org_id == ctx.org_id,
                                                       ExchangeRate.currency_code == c.code,
                                                       ExchangeRate.rate_date == body.rate_date))).scalar_one_or_none()  # fmt: skip
    before = row.to_dict() if row else None
    if row is None:
        row = ExchangeRate(
            org_id=ctx.org_id, currency_code=c.code, rate_date=body.rate_date, rate_to_base=body.rate_to_base
        )
        db.add(row)
    else:
        row.rate_to_base = body.rate_to_base
    await db.flush()
    await _audit(db, ctx, "UPDATE" if before else "CREATE", "exchange_rate", row.id, before, row.to_dict())
    return await _currency_out(db, c)


# ================================================================= godowns
def _godown_out(g: Godown) -> GodownOut:
    return GodownOut(id=g.id, name=g.name, parent_godown_id=g.parent_godown_id, godown_type=g.godown_type,
                     is_system=g.is_system)  # fmt: skip


async def list_godowns(db: AsyncSession, ctx: TenantContext) -> list[GodownOut]:
    f = await acl_list_filter(ctx, db, "GODOWN", "accounts.inventory_masters")
    return [_godown_out(g) for g in await repo.list_all(db, Godown, ctx.org_id, Godown.name) if f.visible(g.id)]


async def create_godown(db: AsyncSession, ctx: TenantContext, body: GodownIn) -> GodownOut:
    if body.parent_godown_id:
        await _must(db, Godown, ctx, body.parent_godown_id)
    if await repo.name_taken(db, Godown, ctx.org_id, body.name):
        raise AlreadyExistsError("A godown with this name already exists")
    g = Godown(org_id=ctx.org_id, name=body.name, parent_godown_id=body.parent_godown_id,
               godown_type=body.godown_type.upper(), is_system=False)  # fmt: skip
    await repo.add(db, g)
    await _audit(db, ctx, "CREATE", "godown", g.id, after=g.to_dict())
    return _godown_out(g)


async def update_godown(db: AsyncSession, ctx: TenantContext, godown_id: uuid.UUID, body: GodownIn) -> GodownOut:
    g = await _must(db, Godown, ctx, godown_id)
    await assert_resource_access(ctx, db, "GODOWN", g.id, "accounts.inventory_masters", "WRITE")
    before = g.to_dict()
    if g.is_system and ("godown_type" in body.model_fields_set and body.godown_type.upper() != g.godown_type
                        or "parent_godown_id" in body.model_fields_set and body.parent_godown_id):  # fmt: skip
        raise SystemRecordError("System godowns can only be renamed")
    if body.name != g.name and await repo.name_taken(db, Godown, ctx.org_id, body.name, exclude=g.id):
        raise AlreadyExistsError("A godown with this name already exists")
    if body.parent_godown_id == g.id:
        raise ValidationFailedError("A godown cannot be its own parent")
    if body.parent_godown_id:
        await _must(db, Godown, ctx, body.parent_godown_id)
    g.name = body.name
    if not g.is_system:
        g.parent_godown_id, g.godown_type = body.parent_godown_id, body.godown_type.upper()
    await db.flush()
    await _audit(db, ctx, "UPDATE", "godown", g.id, before, g.to_dict())
    return _godown_out(g)


async def delete_godown(db: AsyncSession, ctx: TenantContext, godown_id: uuid.UUID) -> None:
    g = await _must(db, Godown, ctx, godown_id)
    await assert_resource_access(ctx, db, "GODOWN", g.id, "accounts.inventory_masters", "FULL")
    if g.is_system:
        raise SystemRecordError("System godowns cannot be deleted")
    if await repo.exists(db, select(VoucherInventoryEntry.id).where(VoucherInventoryEntry.org_id == ctx.org_id,
                                                                    VoucherInventoryEntry.godown_id == g.id)) or \
            await repo.exists(db, select(Godown.id).where(Godown.parent_godown_id == g.id)):  # fmt: skip
        raise ConflictError("The godown is in use")
    before = g.to_dict()
    await db.delete(g)
    await db.flush()
    await _audit(db, ctx, "DELETE", "godown", godown_id, before=before)


# ================================================================= stock groups
async def list_stock_groups(db: AsyncSession, ctx: TenantContext) -> list[StockGroupOut]:
    return [StockGroupOut.model_validate(g) for g in await repo.list_all(db, StockGroup, ctx.org_id, StockGroup.name)]


async def create_stock_group(db: AsyncSession, ctx: TenantContext, body: StockGroupIn) -> StockGroupOut:
    if body.parent_id:
        await _must(db, StockGroup, ctx, body.parent_id)
    if await repo.name_taken(db, StockGroup, ctx.org_id, body.name):
        raise AlreadyExistsError("A stock group with this name already exists")
    g = StockGroup(org_id=ctx.org_id, name=body.name, parent_id=body.parent_id)
    await repo.add(db, g)
    await _audit(db, ctx, "CREATE", "stock_group", g.id, after=g.to_dict())
    return StockGroupOut.model_validate(g)


async def update_stock_group(db: AsyncSession, ctx: TenantContext, sg_id: uuid.UUID, body: StockGroupIn
                             ) -> StockGroupOut:  # fmt: skip
    g = await _must(db, StockGroup, ctx, sg_id)
    before = g.to_dict()
    if body.name != g.name and await repo.name_taken(db, StockGroup, ctx.org_id, body.name, exclude=g.id):
        raise AlreadyExistsError("A stock group with this name already exists")
    if body.parent_id:
        cur = await _must(db, StockGroup, ctx, body.parent_id)
        while cur is not None:
            if cur.id == g.id:
                raise ValidationFailedError("A stock group cannot be moved under itself")
            cur = await repo.get(db, StockGroup, ctx.org_id, cur.parent_id)
    g.name, g.parent_id = body.name, body.parent_id
    await db.flush()
    await _audit(db, ctx, "UPDATE", "stock_group", g.id, before, g.to_dict())
    return StockGroupOut.model_validate(g)


async def delete_stock_group(db: AsyncSession, ctx: TenantContext, sg_id: uuid.UUID) -> None:
    g = await _must(db, StockGroup, ctx, sg_id)
    if await repo.exists(db, select(StockItem.id).where(StockItem.org_id == ctx.org_id, StockItem.stock_group_id == g.id)) or \
            await repo.exists(db, select(StockGroup.id).where(StockGroup.parent_id == g.id)):  # fmt: skip
        raise ConflictError("The stock group has items or sub-groups")
    before = g.to_dict()
    await db.delete(g)
    await db.flush()
    await _audit(db, ctx, "DELETE", "stock_group", sg_id, before=before)


# ================================================================= stock items
KEY = "accounts.inventory_masters"


async def item_outs(db: AsyncSession, ctx: TenantContext, items: list[StockItem]) -> list[StockItemOut]:
    vals = await valuations(db, ctx.org_id, items)
    group_names = {g.id: g.name for g in await repo.list_all(db, StockGroup, ctx.org_id, StockGroup.name)}
    out = []
    for i in items:
        url = i.engineering_diagram_url
        if i.diagram_storage_key:
            url = (await get_storage().create_download_url(i.diagram_storage_key)).url
        v = vals[i.id]
        out.append(StockItemOut(id=i.id, target_type=i.target_type, name=i.name, sku_code=i.sku_code,
                                stock_group_id=i.stock_group_id, stock_group_name=group_names.get(i.stock_group_id),
                                uom_primary=i.uom_primary, uom_alternate=i.uom_alternate,
                                uom_conversion_factor=i.uom_conversion_factor, valuation_method=i.valuation_method,
                                hsn_sac_code=i.hsn_sac_code, gst_rate=i.gst_rate, opening_qty=i.opening_qty,
                                opening_rate=i.opening_rate, reorder_level=i.reorder_level, diagram_url=url,
                                custom_fields=i.custom_fields or {}, bom_components=list(i.bom_components or []),
                                closing_qty=v.closing_qty, closing_value=v.closing_value,
                                created_at=i.created_at))  # fmt: skip
    return out


async def list_stock_items(db: AsyncSession, ctx: TenantContext, page: PageParams, *, q: str | None,
                           stock_group_id: uuid.UUID | None, target_type: str | None) -> Page[StockItemOut]:  # fmt: skip
    f = await acl_list_filter(ctx, db, "STOCK_ITEM", KEY)
    stmt = select(StockItem).where(StockItem.org_id == ctx.org_id, f.clause(StockItem.id)).order_by(StockItem.name)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(StockItem.name.ilike(like), StockItem.sku_code.ilike(like)))
    if stock_group_id:
        stmt = stmt.where(StockItem.stock_group_id == stock_group_id)
    if target_type:
        stmt = stmt.where(StockItem.target_type == target_type)
    rows, total = await repo.page_scalars(db, stmt, page)
    return Page[StockItemOut](items=await item_outs(db, ctx, rows), total=total, limit=page.limit, offset=page.offset)


async def get_stock_item(db: AsyncSession, ctx: TenantContext, item_id: uuid.UUID) -> StockItemOut:
    item = await _must(db, StockItem, ctx, item_id)
    await assert_resource_access(ctx, db, "STOCK_ITEM", item.id, KEY, "READ")
    return (await item_outs(db, ctx, [item]))[0]


async def _validate_item(db: AsyncSession, ctx: TenantContext, body: StockItemIn, item_id: uuid.UUID | None) -> None:
    key = body.diagram_storage_key
    if key and (not key.startswith(f"org/{ctx.org_id}/") or await get_storage().head(key) is None):
        raise ValidationFailedError("The file was not uploaded for this organization", {"field": "diagram_storage_key"})
    if body.stock_group_id:
        await _must(db, StockGroup, ctx, body.stock_group_id)
    raw_ids = [c.raw_item_id for c in body.bom_components]
    if item_id in raw_ids:
        raise ValidationFailedError("An item cannot be a component of itself")
    if raw_ids and len(await repo.get_many(db, StockItem, ctx.org_id, raw_ids)) != len(set(raw_ids)):
        raise ValidationFailedError("A BOM component item does not exist")


def _apply_item(item: StockItem, body: StockItemIn, fields: set[str]) -> None:
    for f in ("target_type", "name", "sku_code", "stock_group_id", "uom_primary", "uom_alternate",
              "uom_conversion_factor", "valuation_method", "hsn_sac_code", "gst_rate", "opening_qty", "opening_rate",
              "reorder_level", "diagram_storage_key", "custom_fields"):  # fmt: skip
        if f in fields:
            setattr(item, f, getattr(body, f))
    if "bom_components" in fields:
        item.bom_components = [c.model_dump(mode="json") for c in body.bom_components]


async def create_stock_item(db: AsyncSession, ctx: TenantContext, body: StockItemIn) -> StockItemOut:
    await _validate_item(db, ctx, body, None)
    if await repo.name_taken(db, StockItem, ctx.org_id, body.name):
        raise AlreadyExistsError("A stock item with this name already exists")
    item = StockItem(org_id=ctx.org_id)
    _apply_item(item, body, set(StockItemIn.model_fields))
    await repo.add(db, item)
    await db.refresh(item)
    await _audit(db, ctx, "CREATE", "stock_item", item.id, after=item.to_dict())
    return (await item_outs(db, ctx, [item]))[0]


async def update_stock_item(db: AsyncSession, ctx: TenantContext, item_id: uuid.UUID, body: StockItemIn
                            ) -> StockItemOut:  # fmt: skip
    item = await _must(db, StockItem, ctx, item_id)
    await assert_resource_access(ctx, db, "STOCK_ITEM", item.id, KEY, "WRITE")
    return await apply_item_update(db, ctx, item, body)


async def apply_item_update(db: AsyncSession, ctx: TenantContext, item: StockItem, body: StockItemIn) -> StockItemOut:
    """Update without the accounts-side ACL check (callers authorise; used by the operations items facade)."""
    await _validate_item(db, ctx, body, item.id)
    if body.name != item.name and await repo.name_taken(db, StockItem, ctx.org_id, body.name, exclude=item.id):
        raise AlreadyExistsError("A stock item with this name already exists")
    before = item.to_dict()
    _apply_item(item, body, body.model_fields_set | {"name"})
    await db.flush()
    await _audit(db, ctx, "UPDATE", "stock_item", item.id, before, item.to_dict())
    return (await item_outs(db, ctx, [item]))[0]


async def delete_stock_item(db: AsyncSession, ctx: TenantContext, item_id: uuid.UUID) -> None:
    item = await _must(db, StockItem, ctx, item_id)
    await assert_resource_access(ctx, db, "STOCK_ITEM", item.id, KEY, "FULL")
    if await repo.exists(db, select(VoucherInventoryEntry.id).where(VoucherInventoryEntry.org_id == ctx.org_id,
                                                                    VoucherInventoryEntry.stock_item_id == item.id)):  # fmt: skip
        raise ConflictError("The stock item has inventory transactions")
    for other in await repo.list_all(db, StockItem, ctx.org_id, StockItem.name):
        if any(str(c.get("raw_item_id")) == str(item.id) for c in other.bom_components or []):
            raise ConflictError(f"The item is a BOM component of {other.name}")
    before = item.to_dict()
    await db.delete(item)
    await db.flush()
    await _audit(db, ctx, "DELETE", "stock_item", item_id, before=before)


async def stock_item_upload_url(ctx: TenantContext, body: StockItemUploadIn) -> UploadTicket:
    validate_upload(body.content_type, body.size_bytes, DOCUMENT_MIME_ALLOWLIST)
    t = await get_storage().create_upload_ticket(build_org_key(ctx.org_id, body.file_name), body.content_type,
                                                 body.size_bytes)  # fmt: skip
    return UploadTicket(upload_url=t.upload_url, method=t.method, headers=t.headers, storage_key=t.storage_key,
                        expires_at=t.expires_at)  # fmt: skip


# ================================================================= settings
SETTINGS_KEYS = tuple(AccountsSettings.model_fields)


async def get_settings(db: AsyncSession, ctx: TenantContext) -> AccountsSettings:
    org = await common.org_brief(db, ctx)
    raw = {k: v for k, v in (org.accounts_settings or {}).items() if k in SETTINGS_KEYS}
    return AccountsSettings.model_validate(raw)


async def put_settings(db: AsyncSession, ctx: TenantContext, body: AccountsSettings) -> AccountsSettings:
    org = await common.org_brief(db, ctx)
    for vt_id in (body.default_sales_voucher_type_id, body.default_purchase_voucher_type_id):
        if vt_id:
            await _must(db, VoucherType, ctx, vt_id)
    before = dict(org.accounts_settings or {})
    merged = {**before, **body.model_dump(mode="json")}
    await organization.update_accounts_settings(db, ctx, merged)
    await _audit(db, ctx, "UPDATE", "accounts_settings", ctx.org_id, before, merged)
    if before.get("books_locked_until") != merged.get("books_locked_until"):
        action = "LOCK" if merged.get("books_locked_until") else "UNLOCK"
        await write_audit(db, ctx, M, action, "books_period", ctx.org_id,
                          before={"books_locked_until": before.get("books_locked_until")},
                          after={"books_locked_until": merged.get("books_locked_until")})  # fmt: skip
    return body
