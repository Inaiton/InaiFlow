"""Banking: bank accounts, BRS view, manual reconciliation, statement import + auto-match, cheque books/register/print.

Statement debit (withdrawal) matches a book CR on the bank ledger; statement credit (deposit) matches a book DR.
Auto-match: same amount, opposite-view side, value/txn date within ±3 days of the voucher date; an instrument
number equal to the statement reference wins; otherwise the nearest date; ties stay unmatched.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.export import Letterhead, Report, get_exporter
from app.core.audit import write_audit
from app.core.context import TenantContext
from app.core.errors import ConflictError, InvalidStateError, NotFoundError, ValidationFailedError
from app.core.money import ZERO, to_str
from app.core.pagination import Page, PageParams
from app.modules.accounts import common
from app.modules.accounts import repository as repo
from app.modules.accounts.bank_parsers import StatementParseError, dedupe_hash, detect_format, parse_statement
from app.modules.accounts.ledger_math import Chart, split
from app.modules.accounts.models import (
    BankStatementImport,
    BankStatementLine,
    ChequeBook,
    Ledger,
    Voucher,
    VoucherEntry,
    VoucherType,
)
from app.modules.accounts.schemas import (
    BankAccountOut,
    ChequeBookIn,
    ChequeBookOut,
    ChequeOut,
    ReconciliationOut,
    ReconEntryOut,
    StatementImportOut,
    StatementLineOut,
)
from app.modules.accounts.service import _particulars
from app.modules.accounts.words import amount_in_words

M = "ACCOUNTS"
MAX_STATEMENT_BYTES = 5 * 1024 * 1024
MATCH_WINDOW = timedelta(days=3)


async def _bank_ledger(db: AsyncSession, ctx: TenantContext, ledger_id: uuid.UUID) -> tuple[Ledger, Chart]:
    lg = await repo.get(db, Ledger, ctx.org_id, ledger_id)
    if lg is None:
        raise NotFoundError()
    chart = await repo.load_chart(db, ctx.org_id)
    if lg.group_id not in chart.subtree("BANK_ACCOUNTS", "BANK_OD"):
        raise ValidationFailedError("The ledger is not a bank account")
    return lg, chart


def _line_out(ln: BankStatementLine) -> StatementLineOut:
    return StatementLineOut(id=ln.id, txn_date=ln.txn_date, value_date=ln.value_date, description=ln.description,
                            reference=ln.reference, debit=ln.debit, credit=ln.credit, balance=ln.balance,
                            status=ln.status, matched_entry_id=ln.matched_entry_id)  # fmt: skip


async def _bank_rows(
    db: AsyncSession, ctx: TenantContext, ledger_ids: list[uuid.UUID], as_of: date | None
) -> list[Any]:
    return await repo.ledger_entries(db, ctx.org_id, ledger_ids, None, as_of)


async def _recon_outs(db: AsyncSession, ctx: TenantContext, chart: Chart, rows: list[Any]) -> list[ReconEntryOut]:
    others = await repo.entries_of_vouchers(db, list({r[1].id for r in rows}))
    names = {i: n.name for i, n in chart.ledgers.items()}
    return [ReconEntryOut(entry_id=e.id, voucher_id=v.id, voucher_number=v.voucher_number, voucher_type=vt,
                          voucher_date=v.voucher_date, particulars=_particulars(others[v.id], e.ledger_id, e.entry_type, names),
                          debit=e.amount if e.entry_type == "DR" else ZERO, credit=e.amount if e.entry_type == "CR" else ZERO,
                          instrument_no=e.instrument_no, instrument_date=e.instrument_date,
                          bank_reconciliation_date=e.bank_reconciliation_date) for e, v, vt, _b in rows]  # fmt: skip


async def list_bank_accounts(db: AsyncSession, ctx: TenantContext) -> list[BankAccountOut]:
    chart = await repo.load_chart(db, ctx.org_id)
    banks = sorted(chart.ledgers_in("BANK_ACCOUNTS", "BANK_OD"), key=lambda lg: lg.name)
    bal = await repo.balances(db, chart, ctx.org_id, None)
    rows = await _bank_rows(db, ctx, [b.id for b in banks], None)
    out = []
    for b in banks:
        mine = [r[0] for r in rows if r[0].ledger_id == b.id]
        amount, kind = split(bal[b.id])
        recon = [e.bank_reconciliation_date for e in mine if e.bank_reconciliation_date]
        out.append(BankAccountOut(ledger_id=b.id, name=b.name, bank_account=b.party_details.get("bank_account"),
                                  ifsc=b.party_details.get("ifsc"), book_balance=amount, book_balance_type=kind,
                                  unreconciled_count=sum(1 for e in mine if e.bank_reconciliation_date is None),
                                  last_reconciled_on=max(recon) if recon else None))  # fmt: skip
    return out


async def reconciliation(db: AsyncSession, ctx: TenantContext, ledger_id: uuid.UUID, as_of: date,
                         show: str | None) -> ReconciliationOut:  # fmt: skip
    lg, chart = await _bank_ledger(db, ctx, ledger_id)
    show = (show or "unreconciled").lower()
    if show not in ("unreconciled", "reconciled", "all"):
        raise ValidationFailedError("show must be unreconciled, reconciled or all")
    rows = await _bank_rows(db, ctx, [lg.id], as_of)
    books = chart.ledgers[lg.id].opening + sum(
        (e.amount if e.entry_type == "DR" else -e.amount for e, *_ in rows), ZERO
    )
    pending = [r for r in rows if r[0].bank_reconciliation_date is None or r[0].bank_reconciliation_date > as_of]
    not_reflected = sum((e.amount if e.entry_type == "DR" else -e.amount for e, *_ in pending), ZERO)
    picked = {"unreconciled": pending, "all": rows,
              "reconciled": [r for r in rows if r not in pending]}[show]  # fmt: skip
    lines = (await db.execute(select(BankStatementLine).where(
        BankStatementLine.org_id == ctx.org_id, BankStatementLine.bank_ledger_id == lg.id,
        BankStatementLine.status == "UNMATCHED", BankStatementLine.txn_date <= as_of)
        .order_by(BankStatementLine.txn_date))).scalars().all()  # fmt: skip
    amount, kind = split(books)
    return ReconciliationOut(ledger_id=lg.id, as_of=as_of, balance_as_per_books=amount, books_type=kind,
                             amounts_not_reflected_in_bank=not_reflected, balance_as_per_bank=books - not_reflected,
                             entries=await _recon_outs(db, ctx, chart, picked),
                             statement_lines=[_line_out(ln) for ln in lines])  # fmt: skip


async def _bank_entry(db: AsyncSession, ctx: TenantContext, entry_id: uuid.UUID) -> tuple[VoucherEntry, Voucher, Chart]:
    row = (await db.execute(select(VoucherEntry, Voucher).join(Voucher, Voucher.id == VoucherEntry.voucher_id)
                            .where(VoucherEntry.id == entry_id, VoucherEntry.org_id == ctx.org_id))).first()  # fmt: skip
    if row is None:
        raise NotFoundError()
    e, v = row
    chart = await repo.load_chart(db, ctx.org_id)
    if e.ledger_id not in {lg.id for lg in chart.ledgers_in("BANK_ACCOUNTS", "BANK_OD")}:
        raise ValidationFailedError("The entry is not on a bank ledger")
    if v.status != "REGULAR":
        raise InvalidStateError("Only regular vouchers can be reconciled")
    return e, v, chart


async def reconcile_entry(db: AsyncSession, ctx: TenantContext, entry_id: uuid.UUID, recon_date: date | None
                          ) -> ReconEntryOut:  # fmt: skip
    e, v, chart = await _bank_entry(db, ctx, entry_id)
    if recon_date is not None and recon_date < v.voucher_date:
        raise ValidationFailedError("The bank date cannot be before the voucher date")
    before = {"bank_reconciliation_date": e.bank_reconciliation_date}
    e.bank_reconciliation_date = recon_date
    await db.flush()
    await write_audit(db, ctx, M, "UPDATE", "voucher_entry", e.id, before=before,
                      after={"bank_reconciliation_date": recon_date})  # fmt: skip
    rows = [r for r in await repo.ledger_entries(db, ctx.org_id, [e.ledger_id], v.voucher_date, v.voucher_date)
            if r[0].id == e.id]  # fmt: skip
    return (await _recon_outs(db, ctx, chart, rows))[0]


# ---------------------------------------------------------------- statement import + matching
async def import_statement(db: AsyncSession, ctx: TenantContext, ledger_id: uuid.UUID, data: bytes,
                           file_name: str | None) -> StatementImportOut:  # fmt: skip
    lg, _ = await _bank_ledger(db, ctx, ledger_id)
    if len(data) > MAX_STATEMENT_BYTES:
        raise ValidationFailedError("Statement files are limited to 5 MB")
    org = await common.org_brief(db, ctx)
    columns = (org.accounts_settings or {}).get("bank_csv_columns") or None
    try:
        fmt = detect_format(data, file_name)
        parsed = parse_statement(data, file_name, columns=columns)
    except StatementParseError as exc:
        raise ValidationFailedError(str(exc)) from exc
    existing = set((await db.execute(select(BankStatementLine.dedupe_hash).where(
        BankStatementLine.org_id == ctx.org_id, BankStatementLine.bank_ledger_id == lg.id))).scalars())  # fmt: skip
    imp = BankStatementImport(org_id=ctx.org_id, bank_ledger_id=lg.id, file_name=(file_name or "statement")[:255],
                              format=fmt, imported_by=ctx.user_id)  # fmt: skip
    await repo.add(db, imp)
    created, dupes = [], 0
    for p in parsed:
        h = dedupe_hash(lg.id, p)
        if h in existing:
            dupes += 1
            continue
        existing.add(h)
        ln = BankStatementLine(org_id=ctx.org_id, import_id=imp.id, bank_ledger_id=lg.id, txn_date=p.txn_date,
                               value_date=p.value_date, description=p.description[:2000], reference=(p.reference or None),
                               debit=p.debit, credit=p.credit, balance=p.balance, status="UNMATCHED", dedupe_hash=h)  # fmt: skip
        db.add(ln)
        created.append(ln)
    imp.line_count = len(created)
    await db.flush()
    matched = await auto_match(db, ctx, lg.id, created)
    await write_audit(db, ctx, M, "CREATE", "bank_statement_import", imp.id,
                      after={"file_name": imp.file_name, "format": fmt, "lines": len(created), "duplicates": dupes,
                             "auto_matched": matched})  # fmt: skip
    return StatementImportOut(import_id=imp.id, format=fmt, lines_imported=len(created), auto_matched=matched,
                              duplicates_skipped=dupes)  # fmt: skip


def _norm_ref(s: str | None) -> str:
    return (s or "").strip().lstrip("0").upper()


async def auto_match(db: AsyncSession, ctx: TenantContext, ledger_id: uuid.UUID, lines: list[BankStatementLine]) -> int:
    taken = set((await db.execute(select(BankStatementLine.matched_entry_id).where(
        BankStatementLine.org_id == ctx.org_id, BankStatementLine.matched_entry_id.is_not(None)))).scalars())  # fmt: skip
    candidates = [r for r in await repo.ledger_entries(db, ctx.org_id, [ledger_id], None, None)
                  if r[0].bank_reconciliation_date is None and r[0].id not in taken]  # fmt: skip
    matched = 0
    for ln in lines:
        side, amount = ("CR", ln.debit) if ln.debit > 0 else ("DR", ln.credit)
        on = ln.value_date or ln.txn_date
        pool = [r for r in candidates if r[0].entry_type == side and r[0].amount == amount
                and abs((r[1].voucher_date - on).days) <= MATCH_WINDOW.days and r[0].id not in taken]  # fmt: skip
        if not pool:
            continue
        ref = _norm_ref(ln.reference)
        by_ref = [r for r in pool if ref and _norm_ref(r[0].instrument_no) == ref]
        if len(by_ref) == 1:
            pick = by_ref[0]
        else:
            pool.sort(key=lambda r: abs((r[1].voucher_date - on).days))
            if len(pool) > 1 and abs((pool[0][1].voucher_date - on).days) == abs((pool[1][1].voucher_date - on).days):
                continue
            pick = pool[0]
        _apply_match(ln, pick[0])
        taken.add(pick[0].id)
        matched += 1
    await db.flush()
    return matched


def _apply_match(ln: BankStatementLine, e: VoucherEntry) -> None:
    ln.status, ln.matched_entry_id = "MATCHED", e.id
    e.bank_reconciliation_date = ln.value_date or ln.txn_date


async def statement_lines(db: AsyncSession, ctx: TenantContext, ledger_id: uuid.UUID, status: str | None,
                          page: PageParams) -> Page[StatementLineOut]:  # fmt: skip
    lg, _ = await _bank_ledger(db, ctx, ledger_id)
    stmt = select(BankStatementLine).where(
        BankStatementLine.org_id == ctx.org_id, BankStatementLine.bank_ledger_id == lg.id
    )
    if status:
        stmt = stmt.where(BankStatementLine.status == status.upper())
    stmt = stmt.order_by(BankStatementLine.txn_date.desc(), BankStatementLine.id)
    rows, total = await repo.page_scalars(db, stmt, page)
    return Page[StatementLineOut](items=[_line_out(r) for r in rows], total=total, limit=page.limit, offset=page.offset)


async def _line(db: AsyncSession, ctx: TenantContext, line_id: uuid.UUID) -> BankStatementLine:
    ln = await repo.get(db, BankStatementLine, ctx.org_id, line_id)
    if ln is None:
        raise NotFoundError()
    return ln


async def match_line(db: AsyncSession, ctx: TenantContext, line_id: uuid.UUID, entry_id: uuid.UUID) -> StatementLineOut:
    ln = await _line(db, ctx, line_id)
    if ln.status == "MATCHED":
        raise InvalidStateError("The statement line is already matched; unmatch it first")
    e, _v, _c = await _bank_entry(db, ctx, entry_id)
    if e.ledger_id != ln.bank_ledger_id:
        raise ValidationFailedError("The entry belongs to another bank ledger")
    side, amount = ("CR", ln.debit) if ln.debit > 0 else ("DR", ln.credit)
    if e.entry_type != side or e.amount != amount:
        raise ValidationFailedError("Amount or side does not match the statement line")
    if await repo.exists(db, select(BankStatementLine.id).where(BankStatementLine.matched_entry_id == e.id)):
        raise ConflictError("The entry is already matched to another statement line")
    _apply_match(ln, e)
    await db.flush()
    await write_audit(db, ctx, M, "UPDATE", "bank_statement_line", ln.id, after={"status": "MATCHED", "entry_id": e.id})
    return _line_out(ln)


async def unmatch_line(db: AsyncSession, ctx: TenantContext, line_id: uuid.UUID) -> StatementLineOut:
    ln = await _line(db, ctx, line_id)
    if ln.matched_entry_id:
        e = await repo.get(db, VoucherEntry, ctx.org_id, ln.matched_entry_id)
        if e is not None:
            e.bank_reconciliation_date = None
    before = {"status": ln.status, "matched_entry_id": ln.matched_entry_id}
    ln.status, ln.matched_entry_id = "UNMATCHED", None
    await db.flush()
    await write_audit(db, ctx, M, "UPDATE", "bank_statement_line", ln.id, before=before, after={"status": "UNMATCHED"})
    return _line_out(ln)


async def ignore_line(db: AsyncSession, ctx: TenantContext, line_id: uuid.UUID) -> StatementLineOut:
    ln = await _line(db, ctx, line_id)
    if ln.status == "MATCHED":
        raise InvalidStateError("Unmatch the line before ignoring it")
    ln.status = "IGNORED"
    await db.flush()
    await write_audit(db, ctx, M, "UPDATE", "bank_statement_line", ln.id, after={"status": "IGNORED"})
    return _line_out(ln)


# ---------------------------------------------------------------- cheques
async def _cheque_rows(db: AsyncSession, ctx: TenantContext, bank_ids: list[uuid.UUID]) -> list[Any]:
    stmt = (select(VoucherEntry, Voucher).join(Voucher, Voucher.id == VoucherEntry.voucher_id)
            .join(VoucherType, VoucherType.id == Voucher.voucher_type_id)
            .where(VoucherEntry.org_id == ctx.org_id, VoucherEntry.ledger_id.in_(bank_ids),
                   VoucherEntry.instrument_no.is_not(None), VoucherEntry.instrument_no != "")
            .order_by(Voucher.voucher_date, VoucherEntry.instrument_no))  # fmt: skip
    return list((await db.execute(stmt)).all())


def _in_book(no: str | None, b: ChequeBook) -> bool:
    return bool(no) and no.isdigit() and int(b.from_number) <= int(no) <= int(b.to_number)


async def list_cheque_books(
    db: AsyncSession, ctx: TenantContext, bank_ledger_id: uuid.UUID | None
) -> list[ChequeBookOut]:
    stmt = select(ChequeBook).where(ChequeBook.org_id == ctx.org_id).order_by(ChequeBook.created_at)
    if bank_ledger_id:
        stmt = stmt.where(ChequeBook.bank_ledger_id == bank_ledger_id)
    books = list((await db.execute(stmt)).scalars())
    ledgers = await repo.get_many(db, Ledger, ctx.org_id, [b.bank_ledger_id for b in books])
    rows = await _cheque_rows(db, ctx, list({b.bank_ledger_id for b in books})) if books else []
    return [ChequeBookOut(id=b.id, bank_ledger_id=b.bank_ledger_id, bank_name=ledgers[b.bank_ledger_id].name,
                          from_number=b.from_number, to_number=b.to_number, next_number=b.next_number,
                          used_count=len({e.instrument_no for e, _v in rows if e.ledger_id == b.bank_ledger_id
                                          and e.entry_type == "CR" and _in_book(e.instrument_no, b)}),
                          created_at=b.created_at) for b in books]  # fmt: skip


async def create_cheque_book(db: AsyncSession, ctx: TenantContext, body: ChequeBookIn) -> ChequeBookOut:
    lg, _ = await _bank_ledger(db, ctx, body.bank_ledger_id)
    if int(body.from_number) > int(body.to_number):
        raise ValidationFailedError("from_number must not exceed to_number")
    for b in (await db.execute(select(ChequeBook).where(ChequeBook.org_id == ctx.org_id,
                                                        ChequeBook.bank_ledger_id == lg.id))).scalars():  # fmt: skip
        if int(body.from_number) <= int(b.to_number) and int(b.from_number) <= int(body.to_number):
            raise ConflictError("The cheque range overlaps an existing cheque book")
    b = ChequeBook(org_id=ctx.org_id, bank_ledger_id=lg.id, from_number=body.from_number, to_number=body.to_number,
                   next_number=body.from_number)  # fmt: skip
    await repo.add(db, b)
    await write_audit(db, ctx, M, "CREATE", "cheque_book", b.id, after=b.to_dict())
    return next(x for x in await list_cheque_books(db, ctx, lg.id) if x.id == b.id)


async def list_cheques(db: AsyncSession, ctx: TenantContext, bank_ledger_id: uuid.UUID | None,
                       date_from: date | None, date_to: date | None) -> list[ChequeOut]:  # fmt: skip
    chart = await repo.load_chart(db, ctx.org_id)
    banks = [lg.id for lg in chart.ledgers_in("BANK_ACCOUNTS", "BANK_OD")]
    if bank_ledger_id:
        banks = [b for b in banks if b == bank_ledger_id]
    rows = await _cheque_rows(db, ctx, banks) if banks else []
    others = await repo.entries_of_vouchers(db, list({v.id for _e, v in rows}))
    names = {i: n.name for i, n in chart.ledgers.items()}
    out = []
    for e, v in rows:
        if (date_from and v.voucher_date < date_from) or (date_to and v.voucher_date > date_to):
            continue
        payee = names.get(v.party_ledger_id) if v.party_ledger_id else _particulars(others[v.id], e.ledger_id,
                                                                                    e.entry_type, names)  # fmt: skip
        if v.status == "CANCELLED":
            status = "CANCELLED"
        elif e.bank_reconciliation_date:
            status = "CLEARED"
        else:
            status = "ISSUED" if e.entry_type == "CR" else "DEPOSITED"
        out.append(ChequeOut(entry_id=e.id, voucher_id=v.id, voucher_number=v.voucher_number, voucher_date=v.voucher_date,
                             instrument_no=e.instrument_no, instrument_date=e.instrument_date, payee=payee or "",
                             amount=e.amount, bank_ledger_id=e.ledger_id, status=status))  # fmt: skip
    return out


async def print_cheque(db: AsyncSession, ctx: TenantContext, entry_id: uuid.UUID) -> tuple[bytes, str]:
    cheque = next((c for c in await list_cheques(db, ctx, None, None, None) if c.entry_id == entry_id), None)
    if cheque is None:
        raise NotFoundError()
    org = await common.org_brief(db, ctx)
    d = cheque.instrument_date or cheque.voucher_date
    blocks = [
        {"type": "kv", "data": {"rows": [
            {"label": "Date", "value": d.strftime("%d%m%Y")},
            {"label": "Pay", "value": cheque.payee},
            {"label": "Rupees", "value": amount_in_words(cheque.amount)},
            {"label": "Amount", "value": f"**{to_str(cheque.amount)}/-"},
            {"label": "Cheque No", "value": cheque.instrument_no},
        ]}},
        {"type": "paragraph", "data": {"text": "A/c Payee"}},
        {"type": "signature", "data": {"roles": [f"For {org.legal_name}"]}},
    ]  # fmt: skip
    report = Report(title="Cheque", blocks=blocks, letterhead=Letterhead(name=org.legal_name), landscape=True)
    await write_audit(db, ctx, M, "EXPORT", "cheque", entry_id, after={"instrument_no": cheque.instrument_no})
    return get_exporter().render(report, "pdf"), f"cheque-{cheque.instrument_no}.pdf"
