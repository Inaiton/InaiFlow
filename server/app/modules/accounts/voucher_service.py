"""Vouchers: validation (plan §3.8), gap-free numbering under a row lock, create / edit / cancel, attachments,
edit log, print, GST compute-tax, and the system-posting path used by ``accounts.interface``.

Rules enforced here (the deferred DB trigger is only a backstop):
ΣDR == ΣCR (Decimal); >= 2 entries for accounting types (non-accounting types may carry no entries);
ledgers / cost centres / items / godowns belong to the org and ledgers are active; bill allocations <= entry
amount; ``books_locked_until`` -> 423 PERIOD_LOCKED (old and new date on edit); date >= books_beginning_from
and within the current FY (POST_DATED: next FY). Edits keep the number and write before/after + reason.
Cancel sets CANCELLED (excluded everywhere), never deletes.
"""

from __future__ import annotations

import uuid
from collections import OrderedDict
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.export import Letterhead, Report, get_exporter
from app.core.audit import write_audit
from app.core.context import TenantContext
from app.core.errors import (
    DoubleEntryImbalanceError,
    InvalidStateError,
    NotFoundError,
    ValidationFailedError,
)
from app.core.money import ZERO, q2, q4, to_str
from app.core.pagination import Page, PageParams
from app.core.schemas import AuditLogOut
from app.core.sequences import format_number
from app.modules.accounts import common
from app.modules.accounts import repository as repo
from app.modules.accounts.ledger_math import Chart
from app.modules.accounts.models import (
    ChequeBook,
    CostCentre,
    Godown,
    Ledger,
    StockItem,
    Voucher,
    VoucherEntry,
    VoucherInventoryEntry,
    VoucherType,
)
from app.modules.accounts.schemas import (
    ComputeTaxIn,
    ComputeTaxOut,
    DocumentRef,
    EntryIn,
    EntryOut,
    GstIn,
    InventoryOut,
    TaxBreakup,
    VoucherIn,
    VoucherOut,
    VoucherSummary,
)
from app.modules.accounts.words import amount_in_words
from app.modules.documents import interface as documents
from app.modules.identity import interface as identity
from app.modules.organization import interface as organization
from app.modules.platform.interface import get_config
from app.modules.taxation import interface as taxation

M = "ACCOUNTS"
GST_TYPES = ("SALES", "PURCHASE", "CREDIT_NOTE", "DEBIT_NOTE")
PARTY_SIDE = {"SALES": "DR", "DEBIT_NOTE": "DR", "PURCHASE": "CR", "CREDIT_NOTE": "CR"}
OUTWARD_TAX = ("SALES", "CREDIT_NOTE")
TAX_CODES = {
    "OUT": {"CGST": "CGST_OUT", "SGST": "SGST_OUT", "IGST": "IGST_OUT"},
    "IN": {"CGST": "CGST_IN", "SGST": "SGST_IN", "IGST": "IGST_IN"},
}
ALLOWED_STATUSES = ("REGULAR", "OPTIONAL", "MEMORANDUM", "POST_DATED")


# ================================================================= helpers
async def _vt(db: AsyncSession, ctx: TenantContext, vt_id: uuid.UUID, *, lock: bool = False) -> VoucherType:
    vt = await (
        repo.voucher_type_for_update(db, ctx.org_id, vt_id) if lock else repo.get(db, VoucherType, ctx.org_id, vt_id)
    )
    if vt is None:
        raise ValidationFailedError("Unknown voucher type", details={"field": "voucher_type_id"})
    return vt


async def _voucher(db: AsyncSession, ctx: TenantContext, voucher_id: uuid.UUID) -> Voucher:
    v = await repo.get(db, Voucher, ctx.org_id, voucher_id)
    if v is None:
        raise NotFoundError()
    return v


def _gst_head(tax_config: dict | None) -> str | None:
    if tax_config and str(tax_config.get("tax_type", "")).upper() == "GST":
        head = tax_config.get("gst_head")
        return str(head).upper() if head else None
    return None


async def _validate(db: AsyncSession, ctx: TenantContext, vt: VoucherType, body: VoucherIn) -> dict[str, Any]:
    """Returns loaded masters keyed by kind for later use."""
    if body.status not in ALLOWED_STATUSES:
        raise ValidationFailedError("Use the cancel endpoint to cancel a voucher", details={"field": "status"})
    entries = body.entries
    if vt.is_accounting and len(entries) < 2:
        raise ValidationFailedError("An accounting voucher needs at least two ledger entries")
    dr = sum((e.amount for e in entries if e.entry_type == "DR"), ZERO)
    cr = sum((e.amount for e in entries if e.entry_type == "CR"), ZERO)
    if dr != cr:
        raise DoubleEntryImbalanceError(details={"total_debit": to_str(dr), "total_credit": to_str(cr),
                                                 "difference": to_str(dr - cr)})  # fmt: skip
    ledger_ids = {e.ledger_id for e in entries} | ({body.party_ledger_id} if body.party_ledger_id else set())
    ledgers = await repo.get_many(db, Ledger, ctx.org_id, list(ledger_ids))
    for lid in ledger_ids:
        lg = ledgers.get(lid)
        if lg is None:
            raise ValidationFailedError("Ledger not found", details={"ledger_id": str(lid)})
        if not lg.is_active:
            raise ValidationFailedError(f"Ledger {lg.name} is inactive", details={"ledger_id": str(lid)})
    cc_ids = [e.cost_centre_id for e in entries if e.cost_centre_id]
    if len(await repo.get_many(db, CostCentre, ctx.org_id, cc_ids)) != len(set(cc_ids)):
        raise ValidationFailedError("Cost centre not found")
    for i, e in enumerate(entries):
        alloc = sum((a.amount for a in e.bill_allocations), ZERO)
        if alloc > e.amount:
            raise ValidationFailedError("Bill allocations exceed the entry amount", details={"entry": i})
    items = await repo.get_many(db, StockItem, ctx.org_id, [i.stock_item_id for i in body.inventory])
    godowns = await repo.get_many(db, Godown, ctx.org_id, [i.godown_id for i in body.inventory])
    for i, inv in enumerate(body.inventory):
        if inv.stock_item_id not in items:
            raise ValidationFailedError("Stock item not found", details={"inventory": i})
        if inv.godown_id not in godowns:
            raise ValidationFailedError("Godown not found", details={"inventory": i})
    return {"ledgers": ledgers, "items": items, "dr": dr}


def _inv_amount(inv: Any) -> Decimal:
    return q4(inv.amount if inv.amount is not None else inv.quantity * inv.rate)


async def _gst_metadata(db: AsyncSession, ctx: TenantContext, vt: VoucherType, body: VoucherIn,
                        masters: dict[str, Any], previous: dict | None = None) -> dict | None:  # fmt: skip
    """Snapshot used by GST returns: place of supply, split, posted tax per head and the rate/HSN breakup."""
    keep = {k: v for k, v in (previous or {}).items() if k in ("einvoice", "eway_bill", "irn")}
    if vt.base_type not in GST_TYPES:
        return keep or None
    org = await common.org_brief(db, ctx)
    gst = body.gst or GstIn()
    party = masters["ledgers"].get(body.party_ledger_id) if body.party_ledger_id else None
    pd = dict(party.party_details or {}) if party else {}
    pos = taxation.place_of_supply(override=gst.place_of_supply_state_code, party_state=pd.get("state_code"),
                                   party_gstin=pd.get("gstin"), org_state=org.state_code)  # fmt: skip
    is_sez = gst.is_sez or bool(pd.get("is_sez"))
    split_inter = is_sez or gst.is_export or pos != org.state_code
    posted = {"cgst": ZERO, "sgst": ZERO, "igst": ZERO, "cess": ZERO, "rcm": ZERO}
    line_side = "CR" if PARTY_SIDE[vt.base_type] == "DR" else "DR"
    taxable_lines: list[tuple[Decimal, Decimal | None, str | None, Decimal | None, str | None]] = []
    ledgers: dict[uuid.UUID, Ledger] = masters["ledgers"]
    for e in body.entries:
        lg = ledgers[e.ledger_id]
        head = _gst_head(lg.tax_config)
        sign = Decimal(1) if e.entry_type == line_side else Decimal(-1)
        if head in ("CGST", "SGST", "IGST", "CESS"):
            posted[head.lower()] += sign * e.amount
        elif head == "RCM":
            posted["rcm"] += e.amount if e.entry_type != line_side else -e.amount
    if body.inventory:
        for inv in body.inventory:
            item = masters["items"][inv.stock_item_id]
            rate = inv.gst_rate if inv.gst_rate is not None else item.gst_rate
            taxable_lines.append((_inv_amount(inv), rate, item.hsn_sac_code, inv.quantity, item.uom_primary))
    else:
        chart = await repo.load_chart(db, ctx.org_id)
        for e in body.entries:
            lg = ledgers[e.ledger_id]
            if e.ledger_id == body.party_ledger_id or _gst_head(lg.tax_config) or lg.system_code == "ROUND_OFF":
                continue
            if chart.nature(e.ledger_id) not in ("INCOME", "EXPENSES") or e.entry_type != line_side:
                continue
            rate = (lg.tax_config or {}).get("rate")
            taxable_lines.append((e.amount, Decimal(str(rate)) if rate not in (None, "") else None, None, None, None))
    total_taxable = sum((t[0] for t in taxable_lines), ZERO)
    total_tax = posted["cgst"] + posted["sgst"] + posted["igst"]
    if gst.reverse_charge and total_tax == 0:
        total_tax = posted["rcm"]
    breakup = []
    for taxable, rate, hsn, qty, uom in taxable_lines:
        if rate is None:
            rate = q2(total_tax * 100 / total_taxable) if total_taxable else ZERO
        tax = q2(taxable * rate / 100)
        row = {"hsn": hsn, "rate": to_str(rate), "taxable": to_str(taxable), "qty": to_str(qty) if qty else None,
               "uom": uom, "igst": to_str(tax) if split_inter else "0.00",
               "cgst": "0.00" if split_inter else to_str(q2(taxable * rate / 200)),
               "sgst": "0.00" if split_inter else to_str(q2(taxable * rate / 200)), "cess": "0.00"}  # fmt: skip
        breakup.append(row)
    return {**keep, "place_of_supply_state_code": pos, "reverse_charge": gst.reverse_charge,
            "is_export": gst.is_export, "is_sez": is_sez, "tax_split": "INTER" if split_inter else "INTRA",
            "party_gstin": pd.get("gstin"), "party_state_code": pd.get("state_code"),
            "posted": {k: to_str(v) for k, v in posted.items()}, "taxable": to_str(total_taxable),
            "breakup": breakup}  # fmt: skip


async def _allocate_number(db: AsyncSession, ctx: TenantContext, vt_id: uuid.UUID) -> str:
    vt = await _vt(db, ctx, vt_id, lock=True)  # SELECT ... FOR UPDATE serialises concurrent saves
    n = vt.next_number
    number = format_number(vt.prefix, n, vt.zero_padding, vt.suffix)
    while await repo.voucher_number_taken(db, ctx.org_id, vt.id, number):
        n += 1
        number = format_number(vt.prefix, n, vt.zero_padding, vt.suffix)
    vt.next_number = n + 1
    await db.flush()
    return number


def _entry_kwargs(e: EntryIn) -> dict[str, Any]:
    return {"ledger_id": e.ledger_id, "entry_type": e.entry_type, "amount": e.amount, "cost_centre_id": e.cost_centre_id,
            "bill_allocations": [a.model_dump(mode="json") for a in e.bill_allocations],
            "instrument_no": e.instrument_no, "instrument_date": e.instrument_date}  # fmt: skip


def _inv_kwargs(inv: Any, items: dict) -> dict[str, Any]:
    gst_rate = inv.gst_rate if inv.gst_rate is not None else items[inv.stock_item_id].gst_rate
    return {"stock_item_id": inv.stock_item_id, "godown_id": inv.godown_id, "movement_type": inv.movement_type,
            "batch_number": inv.batch_number, "quantity": inv.quantity, "rate": inv.rate,
            "amount": _inv_amount(inv), "gst_rate": gst_rate}  # fmt: skip


async def _advance_cheque_books(db: AsyncSession, ctx: TenantContext, entries: list[EntryIn]) -> None:
    for e in entries:
        if e.entry_type != "CR" or not e.instrument_no or not e.instrument_no.isdigit():
            continue
        books = (await db.execute(select(ChequeBook).where(ChequeBook.org_id == ctx.org_id,
                                                           ChequeBook.bank_ledger_id == e.ledger_id))).scalars()  # fmt: skip
        n = int(e.instrument_no)
        for b in books:
            if int(b.from_number) <= n <= int(b.to_number) and n >= int(b.next_number):
                b.next_number = str(n + 1).zfill(len(b.from_number))
    await db.flush()


async def _snapshot(db: AsyncSession, v: Voucher) -> dict[str, Any]:
    entries = (await repo.entries_of_vouchers(db, [v.id]))[v.id]
    inv = (await repo.inventory_of_vouchers(db, [v.id]))[v.id]
    return {**v.to_dict(), "entries": [e.to_dict() for e in entries], "inventory": [i.to_dict() for i in inv]}


# ================================================================= create / edit / cancel
async def save_voucher(db: AsyncSession, ctx: TenantContext, body: VoucherIn, *, existing: Voucher | None = None,
                       action: str = "CREATE") -> Voucher:  # fmt: skip
    org = await common.org_brief(db, ctx)
    vt = await _vt(db, ctx, body.voucher_type_id)
    status = "MEMORANDUM" if vt.base_type == "MEMORANDUM" else body.status
    common.assert_in_books(org, body.voucher_date, status=status)
    common.assert_period_open(org, body.voucher_date, *([existing.voucher_date] if existing else []))
    masters = await _validate(db, ctx, vt, body)
    total = masters["dr"] or sum((_inv_amount(i) for i in body.inventory), ZERO)
    meta = await _gst_metadata(db, ctx, vt, body, masters, existing.gst_metadata if existing else None)
    now = datetime.now(UTC)
    if existing is None:
        v = Voucher(org_id=ctx.org_id, voucher_type_id=vt.id, voucher_number=await _allocate_number(db, ctx, vt.id),
                    created_by=ctx.user_id or org.owner_user_id)  # fmt: skip
        db.add(v)
    else:
        v = existing
        if v.voucher_type_id != vt.id:
            raise ValidationFailedError("The voucher type of a saved voucher cannot change")
    v.voucher_date, v.party_ledger_id, v.status = body.voucher_date, body.party_ledger_id, status
    v.supplier_invoice_no, v.supplier_invoice_date = body.supplier_invoice_no, body.supplier_invoice_date
    v.narration, v.gst_metadata, v.total_amount = body.narration, meta, total
    v.linked_period_run_id, v.linked_step_id, v.updated_at = body.linked_period_run_id, body.linked_step_id, now
    await db.flush()
    await _replace_lines(db, ctx, v, body, masters["items"])
    await _advance_cheque_books(db, ctx, body.entries)
    for doc_id in body.attachment_document_ids:
        await _attach(db, ctx, v.id, doc_id)
    return v


async def _replace_lines(db: AsyncSession, ctx: TenantContext, v: Voucher, body: VoucherIn, items: dict) -> None:
    """Update entries in place when (ledger, side, amount) match so bank reconciliation survives edits."""
    old = (await repo.entries_of_vouchers(db, [v.id]))[v.id]
    pool: dict[tuple, list[VoucherEntry]] = {}
    for e in old:
        pool.setdefault((e.ledger_id, e.entry_type, e.amount), []).append(e)
    for e in body.entries:
        match = pool.get((e.ledger_id, e.entry_type, e.amount))
        row = match.pop(0) if match else VoucherEntry(org_id=ctx.org_id, voucher_id=v.id)
        for k, val in _entry_kwargs(e).items():
            setattr(row, k, val)
        db.add(row)
    for rest in pool.values():
        for e in rest:
            await db.delete(e)
    for i in (await repo.inventory_of_vouchers(db, [v.id]))[v.id]:
        await db.delete(i)
    for inv in body.inventory:
        db.add(VoucherInventoryEntry(org_id=ctx.org_id, voucher_id=v.id, **_inv_kwargs(inv, items)))
    await db.flush()


async def create_voucher(db: AsyncSession, ctx: TenantContext, body: VoucherIn) -> VoucherOut:
    v = await save_voucher(db, ctx, body)
    await write_audit(db, ctx, M, "CREATE", "voucher", v.id, after=await _snapshot(db, v))
    return await get_voucher(db, ctx, v.id)


async def update_voucher(db: AsyncSession, ctx: TenantContext, voucher_id: uuid.UUID, body: VoucherIn) -> VoucherOut:
    v = await _voucher(db, ctx, voucher_id)
    if v.status == "CANCELLED":
        raise InvalidStateError("Cancelled vouchers cannot be edited")
    before = await _snapshot(db, v)
    await save_voucher(db, ctx, body, existing=v)
    await write_audit(db, ctx, M, "UPDATE", "voucher", v.id, before=before, after=await _snapshot(db, v),
                      reason=body.edit_reason)  # fmt: skip
    return await get_voucher(db, ctx, v.id)


async def cancel_voucher(db: AsyncSession, ctx: TenantContext, voucher_id: uuid.UUID, reason: str) -> VoucherOut:
    v = await _voucher(db, ctx, voucher_id)
    if v.status == "CANCELLED":
        raise InvalidStateError("The voucher is already cancelled")
    org = await common.org_brief(db, ctx)
    common.assert_period_open(org, v.voucher_date)
    before = v.to_dict()
    v.status, v.cancel_reason, v.cancelled_at = "CANCELLED", reason, datetime.now(UTC)
    v.updated_at = v.cancelled_at
    await db.execute(text("UPDATE bank_statement_lines SET status = 'UNMATCHED', matched_entry_id = NULL "
                          "WHERE org_id = :o AND matched_entry_id IN (SELECT id FROM voucher_entries WHERE voucher_id = :v)"),
                     {"o": ctx.org_id, "v": v.id})  # fmt: skip
    await db.flush()
    await write_audit(db, ctx, M, "CANCEL", "voucher", v.id, before=before, after=v.to_dict(), reason=reason,
                      changed_only=True)  # fmt: skip
    return await get_voucher(db, ctx, v.id)


# ================================================================= reads
async def summaries(db: AsyncSession, ctx: TenantContext, vouchers: list[Voucher]) -> list[VoucherSummary]:
    vts = await repo.get_many(db, VoucherType, ctx.org_id, [v.voucher_type_id for v in vouchers])
    parties = await repo.get_many(db, Ledger, ctx.org_id, [v.party_ledger_id for v in vouchers if v.party_ledger_id])
    out = []
    for v in vouchers:
        vt = vts[v.voucher_type_id]
        party = parties.get(v.party_ledger_id)
        out.append(VoucherSummary(id=v.id, voucher_number=v.voucher_number, voucher_date=v.voucher_date,
                                  voucher_type_id=vt.id, voucher_type_name=vt.name, base_type=vt.base_type,
                                  party_ledger_id=v.party_ledger_id, party_name=party.name if party else None,
                                  total_amount=v.total_amount, status=v.status, narration=v.narration,
                                  linked_period_run_id=v.linked_period_run_id, created_at=v.created_at))  # fmt: skip
    return out


async def list_vouchers(db: AsyncSession, ctx: TenantContext, page: PageParams, **f: Any) -> Page[VoucherSummary]:
    stmt = (
        select(Voucher).join(VoucherType, VoucherType.id == Voucher.voucher_type_id).where(Voucher.org_id == ctx.org_id)
    )
    if f.get("date_from"):
        stmt = stmt.where(Voucher.voucher_date >= f["date_from"])
    if f.get("date_to"):
        stmt = stmt.where(Voucher.voucher_date <= f["date_to"])
    if f.get("voucher_type_id"):
        stmt = stmt.where(Voucher.voucher_type_id == f["voucher_type_id"])
    if f.get("base_type"):
        stmt = stmt.where(VoucherType.base_type == f["base_type"].upper())
    if f.get("party_ledger_id"):
        stmt = stmt.where(Voucher.party_ledger_id == f["party_ledger_id"])
    if f.get("ledger_id"):
        stmt = stmt.where(
            Voucher.id.in_(select(VoucherEntry.voucher_id).where(VoucherEntry.ledger_id == f["ledger_id"]))
        )
    if f.get("status"):
        stmt = stmt.where(Voucher.status == f["status"])
    if f.get("linked_period_run_id"):
        stmt = stmt.where(Voucher.linked_period_run_id == f["linked_period_run_id"])
    if f.get("q"):
        like = f"%{f['q'].strip()}%"
        stmt = stmt.where(or_(Voucher.voucher_number.ilike(like), Voucher.narration.ilike(like),
                              Voucher.supplier_invoice_no.ilike(like),
                              Voucher.party_ledger_id.in_(select(Ledger.id).where(Ledger.org_id == ctx.org_id,
                                                                                  Ledger.name.ilike(like)))))  # fmt: skip
    stmt = stmt.order_by(Voucher.voucher_date.desc(), Voucher.created_at.desc())
    rows, total = await repo.page_scalars(db, stmt, page)
    return Page[VoucherSummary](items=await summaries(db, ctx, rows), total=total, limit=page.limit, offset=page.offset)


async def get_voucher(db: AsyncSession, ctx: TenantContext, voucher_id: uuid.UUID) -> VoucherOut:
    v = await _voucher(db, ctx, voucher_id)
    (summary,) = await summaries(db, ctx, [v])
    entries = (await repo.entries_of_vouchers(db, [v.id]))[v.id]
    inv = (await repo.inventory_of_vouchers(db, [v.id]))[v.id]
    ledgers = await repo.get_many(db, Ledger, ctx.org_id, [e.ledger_id for e in entries])
    ccs = await repo.get_many(db, CostCentre, ctx.org_id, [e.cost_centre_id for e in entries if e.cost_centre_id])
    items = await repo.get_many(db, StockItem, ctx.org_id, [i.stock_item_id for i in inv])
    gds = await repo.get_many(db, Godown, ctx.org_id, [i.godown_id for i in inv])
    users = await identity.user_briefs(db, [u for u in (v.created_by, v.approved_by) if u])
    return VoucherOut(
        **summary.model_dump(), supplier_invoice_no=v.supplier_invoice_no,
        supplier_invoice_date=v.supplier_invoice_date, gst_metadata=v.gst_metadata, linked_step_id=v.linked_step_id,
        entries=[EntryOut(id=e.id, ledger_id=e.ledger_id, ledger_name=ledgers[e.ledger_id].name, entry_type=e.entry_type,
                          amount=e.amount, cost_centre_id=e.cost_centre_id,
                          cost_centre_name=ccs[e.cost_centre_id].name if e.cost_centre_id in ccs else None,
                          bill_allocations=list(e.bill_allocations or []), instrument_no=e.instrument_no,
                          instrument_date=e.instrument_date, bank_reconciliation_date=e.bank_reconciliation_date)
                 for e in entries],
        inventory=[InventoryOut(id=i.id, stock_item_id=i.stock_item_id, stock_item_name=items[i.stock_item_id].name,
                                uom=items[i.stock_item_id].uom_primary, godown_id=i.godown_id,
                                godown_name=gds[i.godown_id].name, movement_type=i.movement_type, quantity=i.quantity,
                                rate=i.rate, amount=i.amount, batch_number=i.batch_number, gst_rate=i.gst_rate)
                   for i in inv],
        attachments=await _attachments(db, ctx, v.id),
        created_by_name=users[v.created_by].full_name if v.created_by in users else "",
        approved_by_name=users[v.approved_by].full_name if v.approved_by in users else None,
        cancel_reason=v.cancel_reason, updated_at=v.updated_at,
    )  # fmt: skip


# ================================================================= attachments / edit log
async def _attach(db: AsyncSession, ctx: TenantContext, voucher_id: uuid.UUID, document_id: uuid.UUID) -> None:
    await documents.link_document_to_voucher(db, ctx, document_id=document_id, voucher_id=voucher_id)


async def _attachments(db: AsyncSession, ctx: TenantContext, voucher_id: uuid.UUID) -> list[DocumentRef]:
    return [DocumentRef(id=d.id, title=d.title, file_mime_type=d.file_mime_type)
            for d in await documents.list_documents_for_voucher(db, ctx, voucher_id)]  # fmt: skip


async def attach_document(db: AsyncSession, ctx: TenantContext, voucher_id: uuid.UUID, document_id: uuid.UUID
                          ) -> VoucherOut:  # fmt: skip
    v = await _voucher(db, ctx, voucher_id)
    await _attach(db, ctx, v.id, document_id)
    await write_audit(db, ctx, M, "UPDATE", "voucher", v.id, after={"attached_document_id": str(document_id)})
    return await get_voucher(db, ctx, v.id)


async def edit_log(db: AsyncSession, ctx: TenantContext, voucher_id: uuid.UUID) -> list[AuditLogOut]:
    v = await _voucher(db, ctx, voucher_id)
    trail = getattr(organization, "entity_audit_trail", None)
    if trail is not None:
        return await trail(db, ctx, "voucher", v.id)
    rows = list(await db.execute(text(
        "SELECT id, module, action, entity_type, entity_id, actor_type, user_id, role_code, before_diff, after_diff, "
        "reason, ip_address, created_at FROM org_audit_logs WHERE org_id = :o AND entity_type = 'voucher' "
        "AND entity_id = :e ORDER BY created_at, id"), {"o": ctx.org_id, "e": v.id}))  # fmt: skip
    names = {
        k: u.full_name for k, u in (await identity.user_briefs(db, [r.user_id for r in rows if r.user_id])).items()
    }
    return [AuditLogOut(id=r.id, module=r.module, action=r.action, entity_type=r.entity_type, entity_id=r.entity_id,
                        actor_type=r.actor_type, user_id=r.user_id, user_name=names.get(r.user_id),
                        role_code=r.role_code, before_diff=r.before_diff, after_diff=r.after_diff, reason=r.reason,
                        ip_address=str(r.ip_address) if r.ip_address else None, created_at=r.created_at)
            for r in rows]  # fmt: skip


# ================================================================= print
async def print_voucher(
    db: AsyncSession, ctx: TenantContext, voucher_id: uuid.UUID, fmt: str | None
) -> tuple[bytes, str]:
    if fmt and fmt.lower() not in ("pdf",):
        raise ValidationFailedError("Only format=pdf is supported")
    out = await get_voucher(db, ctx, voucher_id)
    org = await common.org_brief(db, ctx)
    settings = org.accounts_settings or {}
    lines = [*org.address_lines, *(f"GSTIN: {org.gstin}" for _ in [0] if org.gstin), org.contact_email]
    blocks: list[dict[str, Any]] = [
        {"type": "heading", "data": {"text": f"{out.voucher_type_name} {out.voucher_number}", "level": 1}},
        {"type": "kv", "data": {"rows": [
            {"label": "Date", "value": out.voucher_date.strftime("%d-%m-%Y")},
            {"label": "Party", "value": out.party_name or "-"},
            {"label": "Status", "value": out.status},
            *([{"label": "Supplier Invoice", "value": out.supplier_invoice_no}] if out.supplier_invoice_no else []),
        ]}},
    ]  # fmt: skip
    if out.inventory:
        blocks.append({"type": "table", "data": {"columns": ["Item", "Godown", "Qty", "Rate", "GST %", "Amount"],
                                                 "rows": [[i.stock_item_name, i.godown_name, f"{to_str(i.quantity)} {i.uom}",
                                                           to_str(i.rate), to_str(i.gst_rate), to_str(i.amount)]
                                                          for i in out.inventory]}})  # fmt: skip
    blocks.append({"type": "table", "data": {"columns": ["Particulars", "Debit", "Credit"],
                                             "rows": [[e.ledger_name, to_str(e.amount) if e.entry_type == "DR" else "",
                                                       to_str(e.amount) if e.entry_type == "CR" else ""]
                                                      for e in out.entries]}})  # fmt: skip
    blocks.append(
        {
            "type": "paragraph",
            "data": {"text": f"Amount: {to_str(out.total_amount)} ({amount_in_words(out.total_amount)})"},
        }
    )
    if out.narration:
        blocks.append({"type": "paragraph", "data": {"text": f"Narration: {out.narration}"}})
    for key, label in (("invoice_bank_details", "Bank details"), ("invoice_terms", "Terms"),
                       ("invoice_declaration", "Declaration")):  # fmt: skip
        if settings.get(key):
            blocks.append({"type": "paragraph", "data": {"text": f"{label}: {settings[key]}"}})
    blocks.append({"type": "signature", "data": {"roles": ["Prepared by", "Authorised signatory"]}})
    report = Report(title=f"{out.voucher_type_name} {out.voucher_number}", blocks=blocks,
                    letterhead=Letterhead(name=org.mailing_name or org.legal_name, lines=[x for x in lines if x]),
                    footer=settings.get("invoice_footer"), watermark="CANCELLED" if out.status == "CANCELLED" else None)  # fmt: skip
    return get_exporter().render(report, "pdf"), f"{out.voucher_number.replace('/', '-')}.pdf"


# ================================================================= compute-tax
async def compute_tax(db: AsyncSession, ctx: TenantContext, body: ComputeTaxIn) -> ComputeTaxOut:
    vt = await _vt(db, ctx, body.voucher_type_id)
    if vt.base_type not in GST_TYPES:
        raise ValidationFailedError("Tax computation applies to Sales, Purchase, Credit Note and Debit Note vouchers")
    org = await common.org_brief(db, ctx)
    chart = await repo.load_chart(db, ctx.org_id)
    party = chart.ledgers.get(body.party_ledger_id)
    if party is None:
        raise ValidationFailedError("Party ledger not found", details={"field": "party_ledger_id"})
    gst = body.gst or GstIn()
    pd = party.party_details
    slabs = (await get_config(db, "GST_SLABS", on_date=body.voucher_date)).get("rates", [])
    items = await repo.get_many(db, StockItem, ctx.org_id, [ln.stock_item_id for ln in body.lines if ln.stock_item_id])
    warnings: list[str] = []
    lines = []
    for ln in body.lines:
        lg = chart.ledgers.get(ln.ledger_id)
        if lg is None:
            raise ValidationFailedError("Line ledger not found", details={"ledger_id": str(ln.ledger_id)})
        item = items.get(ln.stock_item_id) if ln.stock_item_id else None
        if ln.stock_item_id and item is None:
            raise ValidationFailedError("Stock item not found", details={"stock_item_id": str(ln.stock_item_id)})
        rate = ln.gst_rate if ln.gst_rate is not None else (item.gst_rate if item else None)
        if rate is None and (lg.tax_config or {}).get("rate") not in (None, ""):
            rate = Decimal(str(lg.tax_config["rate"]))
        if rate is None:
            warnings.append(f"No GST rate for {lg.name}; 0% applied")
            rate = ZERO
        cf = (item.custom_fields or {}) if item else {}
        lines.append(taxation.GstLine(
            taxable=ln.amount, rate=rate, hsn=ln.hsn_sac_code or (item.hsn_sac_code if item else None), qty=ln.quantity,
            cess_rate=Decimal(str(cf["cess_rate"])) if cf.get("cess_rate") else None,
            cess_per_unit=Decimal(str(cf["cess_per_unit"])) if cf.get("cess_per_unit") else None, key=ln.ledger_id))  # fmt: skip
    if org.gst_reg_type in ("COMPOSITION", "UNREGISTERED") and vt.base_type in OUTWARD_TAX:
        warnings.append("The organization is not a regular GST registrant: no tax is charged on outward supplies")
        lines = [taxation.GstLine(taxable=ln.taxable, rate=ZERO, hsn=ln.hsn, qty=ln.qty, key=ln.key) for ln in lines]
    pos = taxation.place_of_supply(override=gst.place_of_supply_state_code, party_state=pd.get("state_code"),
                                   party_gstin=pd.get("gstin"), org_state=org.state_code)  # fmt: skip
    gctx = taxation.GstContext(org_state=org.state_code, pos_state=pos, slabs=slabs, is_sez=gst.is_sez or bool(pd.get("is_sez")),
                               is_export=gst.is_export, reverse_charge=gst.reverse_charge)  # fmt: skip
    r = taxation.compute_gst(gctx, lines)
    warnings += r.warnings
    if vt.base_type == "SALES" and not pd.get("gstin") and not pd.get("is_unregistered"):
        warnings.append("The party has no GSTIN: the invoice is reported as B2C")
    missing_hsn = [b for b in r.breakup if not b.hsn]
    if missing_hsn:
        warnings.append("HSN/SAC code is missing on some lines")
    entries = _suggest_entries(vt.base_type, chart, party.id, lines, r, gst.reverse_charge, warnings)
    return ComputeTaxOut(tax_split=r.tax_split, taxable_total=r.taxable_total, cgst=r.cgst, sgst=r.sgst, igst=r.igst,
                         cess=r.cess, round_off=r.round_off, invoice_total=r.invoice_total,
                         breakup=[TaxBreakup(hsn_sac_code=b.hsn, gst_rate=b.rate, taxable=b.taxable, cgst=b.cgst,
                                             sgst=b.sgst, igst=b.igst, cess=b.cess) for b in r.breakup],
                         suggested_entries=entries, warnings=sorted(set(warnings)))  # fmt: skip


def _suggest_entries(base_type: str, chart: Chart, party_id: uuid.UUID, lines: list, r: Any, rcm: bool,
                     warnings: list[str]) -> list[EntryIn]:  # fmt: skip
    party_side = PARTY_SIDE[base_type]
    line_side = "CR" if party_side == "DR" else "DR"
    acc: OrderedDict[tuple[uuid.UUID, str], Decimal] = OrderedDict()

    def add(lid: uuid.UUID | None, side: str, amount: Decimal) -> None:
        if lid is None or amount == 0:
            return
        acc[(lid, side)] = acc.get((lid, side), ZERO) + amount

    def code(c: str) -> uuid.UUID | None:
        lid = chart.ledger_by_code.get(c)
        if lid is None:
            warnings.append(f"System ledger {c} is missing")
        return lid

    for ln in lines:
        add(ln.key, line_side, q2(ln.taxable))
    heads = TAX_CODES["OUT" if base_type in OUTWARD_TAX else "IN"]
    for head, amount in (("CGST", r.cgst), ("SGST", r.sgst), ("IGST", r.igst)):
        if amount:
            add(code(heads[head]), line_side, amount)
    if r.cess:
        cess = next((lg.id for lg in chart.ledgers.values() if _gst_head(lg.tax_config) == "CESS"), None)
        if cess is None:
            warnings.append("No ledger with GST head CESS exists for the cess amount")
        add(cess, line_side, r.cess)
    if rcm and r.tax_total:
        add(code("RCM_PAYABLE"), party_side, r.tax_total)
    add(party_id, party_side, r.invoice_total)
    if r.round_off > 0:
        add(code("ROUND_OFF"), line_side, r.round_off)
    elif r.round_off < 0:
        add(code("ROUND_OFF"), party_side, -r.round_off)
    return [EntryIn(ledger_id=lid, entry_type=side, amount=q2(amt)) for (lid, side), amt in acc.items() if amt > 0]


# ================================================================= system postings (accounts.interface)
async def post_system(db: AsyncSession, ctx: TenantContext, *, base_type: str, voucher_date: date, entries: list,
                      inventory: list, narration: str | None, linked_period_run_id: uuid.UUID | None,
                      linked_step_id: uuid.UUID | None, status: str) -> uuid.UUID:  # fmt: skip
    vt = await repo.system_voucher_type(db, ctx.org_id, base_type)
    if vt is None:
        raise ValidationFailedError(f"No voucher type with base_type {base_type}")
    body = VoucherIn(
        voucher_type_id=vt.id, voucher_date=voucher_date, status=status, narration=narration,
        linked_period_run_id=linked_period_run_id, linked_step_id=linked_step_id,
        entries=[EntryIn(ledger_id=e.ledger_id, entry_type=e.entry_type, amount=q4(e.amount),
                         cost_centre_id=e.cost_centre_id, bill_allocations=e.bill_allocations or [])
                 for e in entries if q4(e.amount) > 0],
        inventory=[{"stock_item_id": i.stock_item_id, "godown_id": i.godown_id, "movement_type": i.movement_type,
                    "quantity": q4(i.quantity), "rate": q4(i.rate),
                    "amount": q4(i.amount) if i.amount is not None else None, "batch_number": i.batch_number}
                   for i in inventory if q4(i.quantity) > 0],
    )  # fmt: skip
    v = await save_voucher(db, ctx, body)
    await write_audit(db, ctx, M, "POST", "voucher", v.id, after=await _snapshot(db, v))
    return v.id
