"""Tally XML export (ENVELOPE / TALLYMESSAGE) — GROUP + LEDGER masters and VOUCHER entries in TallyPrime's import
format. Tally signs: debit amounts are negative and flagged ``ISDEEMEDPOSITIVE=Yes``; ledger opening balances
are negative for debit balances."""

from __future__ import annotations

from datetime import date
from xml.etree.ElementTree import Element, SubElement, tostring  # noqa: S405 - building, not parsing

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import write_audit
from app.core.context import TenantContext
from app.core.errors import ValidationFailedError
from app.core.money import to_str
from app.modules.accounts import common
from app.modules.accounts import repository as repo
from app.modules.accounts.models import Ledger
from app.modules.accounts.service import list_groups
from app.modules.accounts.voucher_service import get_voucher


def _el(parent: Element, tag: str, text: str | None = None, **attrs: str) -> Element:
    e = SubElement(parent, tag, attrs)
    if text is not None:
        e.text = text
    return e


async def tally_export(db: AsyncSession, ctx: TenantContext, date_from: date, date_to: date) -> tuple[bytes, str]:
    if date_from > date_to:
        raise ValidationFailedError("date_from must be on or before date_to")
    org = await common.org_brief(db, ctx)
    env = Element("ENVELOPE")
    header = _el(env, "HEADER")
    _el(header, "TALLYREQUEST", "Import Data")
    body = _el(env, "BODY")
    imp = _el(body, "IMPORTDATA")
    desc = _el(imp, "REQUESTDESC")
    _el(desc, "REPORTNAME", "All Masters")
    _el(_el(desc, "STATICVARIABLES"), "SVCURRENTCOMPANY", org.legal_name)
    data = _el(imp, "REQUESTDATA")
    groups = await list_groups(db, ctx)
    gname = {g.id: g.name for g in groups}
    for g in groups:
        if g.is_system_group:
            continue
        msg = _el(data, "TALLYMESSAGE", **{"xmlns:UDF": "TallyUDF"})
        ge = _el(msg, "GROUP", NAME=g.name, ACTION="Create")
        _el(ge, "NAME", g.name)
        _el(ge, "PARENT", gname.get(g.parent_group_id, ""))
    for lg in await repo.list_all(db, Ledger, ctx.org_id, Ledger.name):
        msg = _el(data, "TALLYMESSAGE", **{"xmlns:UDF": "TallyUDF"})
        le = _el(msg, "LEDGER", NAME=lg.name, ACTION="Create")
        _el(le, "NAME", lg.name)
        _el(le, "PARENT", gname.get(lg.group_id, ""))
        ob = lg.opening_balance or 0
        _el(le, "OPENINGBALANCE", to_str(-ob if lg.opening_balance_type == "DR" else ob))
        _el(le, "ISBILLWISEON", "Yes" if lg.maintain_bill_by_bill else "No")
        pd = lg.party_details or {}
        if pd.get("gstin"):
            _el(le, "PARTYGSTIN", pd["gstin"])
        if pd.get("pan"):
            _el(le, "INCOMETAXNUMBER", pd["pan"])
    vouchers = await _vouchers(db, ctx, date_from, date_to)
    for v in vouchers:
        msg = _el(data, "TALLYMESSAGE", **{"xmlns:UDF": "TallyUDF"})
        ve = _el(msg, "VOUCHER", VCHTYPE=v.voucher_type_name, ACTION="Create")
        _el(ve, "DATE", v.voucher_date.strftime("%Y%m%d"))
        _el(ve, "VOUCHERTYPENAME", v.voucher_type_name)
        _el(ve, "VOUCHERNUMBER", v.voucher_number)
        if v.party_name:
            _el(ve, "PARTYLEDGERNAME", v.party_name)
        if v.narration:
            _el(ve, "NARRATION", v.narration)
        for e in v.entries:
            le = _el(ve, "ALLLEDGERENTRIES.LIST")
            _el(le, "LEDGERNAME", e.ledger_name)
            _el(le, "ISDEEMEDPOSITIVE", "Yes" if e.entry_type == "DR" else "No")
            _el(le, "AMOUNT", to_str(-e.amount if e.entry_type == "DR" else e.amount))
            for a in e.bill_allocations:
                ba = _el(le, "BILLALLOCATIONS.LIST")
                _el(ba, "NAME", str(a.get("ref_name", "")))
                _el(ba, "BILLTYPE", {"NEW_REF": "New Ref", "AGAINST_REF": "Agst Ref", "ADVANCE": "Advance",
                                     "ON_ACCOUNT": "On Account"}.get(a.get("ref_type"), "New Ref"))  # fmt: skip
                amt = a.get("amount", "0")
                _el(ba, "AMOUNT", f"-{amt}" if e.entry_type == "DR" else str(amt))
        for i in v.inventory:
            ie = _el(ve, "ALLINVENTORYENTRIES.LIST")
            _el(ie, "STOCKITEMNAME", i.stock_item_name)
            _el(ie, "ISDEEMEDPOSITIVE", "Yes" if i.movement_type == "INWARD" else "No")
            _el(ie, "RATE", f"{to_str(i.rate)}/{i.uom}")
            _el(ie, "ACTUALQTY", f"{to_str(i.quantity)} {i.uom}")
            _el(ie, "AMOUNT", to_str(-i.amount if i.movement_type == "INWARD" else i.amount))
            _el(_el(ie, "BATCHALLOCATIONS.LIST"), "GODOWNNAME", i.godown_name)
    await write_audit(db, ctx, "ACCOUNTS", "EXPORT", "tally_xml", ctx.org_id,
                      after={"date_from": date_from, "date_to": date_to, "vouchers": len(vouchers)})  # fmt: skip
    xml = b'<?xml version="1.0" encoding="UTF-8"?>\n' + tostring(env, encoding="utf-8")
    return xml, f"tally-export-{date_from.isoformat()}-{date_to.isoformat()}.xml"


async def _vouchers(db: AsyncSession, ctx: TenantContext, date_from: date, date_to: date) -> list:
    from sqlalchemy import select

    from app.modules.accounts.models import Voucher

    ids = (await db.execute(select(Voucher.id).where(Voucher.org_id == ctx.org_id, Voucher.status != "CANCELLED",
                                                     Voucher.voucher_date.between(date_from, date_to))
                            .order_by(Voucher.voucher_date, Voucher.created_at))).scalars().all()  # fmt: skip
    return [await get_voucher(db, ctx, i) for i in ids]
