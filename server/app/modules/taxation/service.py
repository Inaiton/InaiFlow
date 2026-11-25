"""GST returns (summary, GSTR-1, GSTR-3B, validator, GSTR-2B import + reconciliation), e-invoice / e-way bill via
``TaxGatewayProvider``, and TDS/TCS (sections, compute, summary, challan, 26Q/27Q/27EQ files).

Voucher data comes only through ``accounts.interface`` (REGULAR vouchers). Per-voucher GST facts: tax per head from
ledgers whose ``tax_config.gst_head`` is CGST/SGST/IGST/CESS/RCM; taxable value, place of supply and the
rate/HSN breakup from ``vouchers.gst_metadata`` (written by accounts on save). API JSON keeps decimals as strings;
the GSTN offline export files carry plain JSON numbers (rendered from Decimal, never float).
"""

from __future__ import annotations

import json
import re
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.taxgateway import get_tax_gateway
from app.core.audit import to_jsonable, write_audit
from app.core.context import TenantContext
from app.core.errors import AlreadyExistsError, InvalidStateError, NotFoundError, ValidationFailedError
from app.core.fy import fy_for_date, month_end, parse_month
from app.core.money import ZERO, q2, to_str
from app.modules.accounts import interface as accounts
from app.modules.accounts.interface import VoucherFullDTO
from app.modules.organization import interface as organization
from app.modules.organization.interface import OrgBrief
from app.modules.platform.interface import get_config
from app.modules.taxation.gst_calc import hsn_for_return, is_valid_gstin, place_of_supply, rate_in_slabs
from app.modules.taxation.models import EinvoiceRecord, Gst2bImport
from app.modules.taxation.schemas import (
    EinvoiceCancelIn,
    EinvoiceOut,
    EwayBillIn,
    Gstr1Out,
    Gstr2bImportOut,
    Gstr2bReconOut,
    Gstr3bOut,
    GstSummaryOut,
    GstTotals,
    GstValidationIssue,
    ReconRow,
    TdsChallanOut,
    TdsComputeIn,
    TdsComputeOut,
    TdsSectionOut,
    TdsSummaryRow,
)
from app.modules.taxation.tds_calc import challan_due_date, compute_tds, fy_quarter

M = "ACCOUNTS"
OUTWARD, INWARD = ("SALES", "CREDIT_NOTE"), ("PURCHASE", "DEBIT_NOTE")
HEADS = ("cgst", "sgst", "igst", "cess")
MAX_2B_BYTES = 10 * 1024 * 1024


# ================================================================= helpers
async def _org(db: AsyncSession, ctx: TenantContext) -> OrgBrief:
    org = await organization.get_org_brief(db, ctx.org_id)
    if org is None:
        raise NotFoundError()
    return org


def _month(period: str) -> tuple[date, date]:
    try:
        start = parse_month(period)
    except ValueError as exc:
        raise ValidationFailedError(str(exc)) from exc
    return start, month_end(start)


def _d(v: Any) -> Decimal:
    try:
        return Decimal(str(v)) if v not in (None, "") else ZERO
    except InvalidOperation:
        return ZERO


def _gstn_date(d: date) -> str:
    return d.strftime("%d-%m-%Y")


@dataclass
class Doc:
    v: VoucherFullDTO
    sign: Decimal  # +1 invoice, -1 note
    taxable: Decimal
    tax: dict[str, Decimal]
    rcm: Decimal
    pos: str
    inter: bool
    gstin: str | None
    export: bool
    sez: bool
    reverse_charge: bool
    rows: list[dict[str, Any]] = field(default_factory=list)  # rate-wise: rate, hsn, taxable, qty, uom, heads

    @property
    def value(self) -> Decimal:
        return self.taxable + sum(self.tax.values(), ZERO)


def _doc(v: VoucherFullDTO, org: OrgBrief) -> Doc:
    meta = v.gst_metadata or {}
    pd = v.party.party_details if v.party else {}
    tax = dict.fromkeys(HEADS, ZERO)
    rcm = ZERO
    for e in v.entries:
        head = str((e["tax_config"] or {}).get("gst_head") or "").lower() if (e["tax_config"] or {}).get(
            "tax_type", "").upper() == "GST" else ""  # fmt: skip
        signed = e["amount"] if e["entry_type"] == "DR" else -e["amount"]
        if head in HEADS:
            tax[head] += signed
        elif head == "rcm":
            rcm += -signed
    tax = {k: abs(x) for k, x in tax.items()}
    rcm = abs(rcm)
    if meta.get("taxable") is not None:
        taxable = _d(meta["taxable"])
    elif v.inventory:
        taxable = sum((i["amount"] for i in v.inventory), ZERO)
    else:
        taxable = sum((e["amount"] for e in v.entries if e["nature"] in ("INCOME", "EXPENSES")
                       and e["system_code"] != "ROUND_OFF" and not (e["tax_config"] or {}).get("gst_head")), ZERO)  # fmt: skip
    pos = meta.get("place_of_supply_state_code") or place_of_supply(
        override=None, party_state=pd.get("state_code"), party_gstin=pd.get("gstin"), org_state=org.state_code)  # fmt: skip
    export, sez = bool(meta.get("is_export")), bool(meta.get("is_sez") or pd.get("is_sez"))
    inter = meta.get("tax_split") == "INTER" if meta.get("tax_split") else (tax["igst"] > 0 or pos != org.state_code)
    total_tax = sum(tax.values(), ZERO) or rcm
    rows = []
    for b in meta.get("breakup") or []:
        rows.append({"rate": _d(b.get("rate")), "hsn": b.get("hsn"), "taxable": _d(b.get("taxable")),
                     "qty": _d(b.get("qty")), "uom": b.get("uom"), "igst": _d(b.get("igst")), "cgst": _d(b.get("cgst")),
                     "sgst": _d(b.get("sgst")), "cess": _d(b.get("cess"))})  # fmt: skip
    if not rows:
        rate = q2(total_tax * 100 / taxable) if taxable else ZERO
        rows = [{"rate": rate, "hsn": None, "taxable": taxable, "qty": ZERO, "uom": None, **tax}]
    sign = Decimal(-1) if v.base_type in ("CREDIT_NOTE", "DEBIT_NOTE") else Decimal(1)
    return Doc(v, sign, taxable, tax, rcm, pos, inter, (pd.get("gstin") or "").upper() or None, export, sez,
               bool(meta.get("reverse_charge")), rows)  # fmt: skip


async def _docs(db: AsyncSession, ctx: TenantContext, start: date, end: date, types: tuple[str, ...]) -> list[Doc]:
    org = await _org(db, ctx)
    vs = await accounts.list_vouchers_full(db, ctx, date_from=start, date_to=end, base_types=list(types))
    return [_doc(v, org) for v in vs]


def _totals(docs: list[Doc], *, rcm_only: bool = False) -> GstTotals:
    t = dict.fromkeys(("taxable", *HEADS), ZERO)
    for d in docs:
        t["taxable"] += d.sign * d.taxable
        if rcm_only:
            key = "igst" if d.inter else None
            if key:
                t["igst"] += d.sign * d.rcm
            else:
                t["cgst"] += d.sign * q2(d.rcm / 2)
                t["sgst"] += d.sign * (d.rcm - q2(d.rcm / 2))
        else:
            for h in HEADS:
                t[h] += d.sign * d.tax[h]
    return GstTotals(**t)


# ================================================================= summary
async def gst_summary(db: AsyncSession, ctx: TenantContext, period: str) -> GstSummaryOut:
    start, end = _month(period)
    docs = await _docs(db, ctx, start, end, OUTWARD + INWARD)
    out = [d for d in docs if d.v.base_type in OUTWARD]
    inn = [d for d in docs if d.v.base_type in INWARD]
    outward, itc, rcm = _totals(out), _totals(inn), _totals([d for d in inn if d.reverse_charge], rcm_only=True)
    net = GstTotals(
        taxable=outward.taxable, **{h: getattr(outward, h) + getattr(rcm, h) - getattr(itc, h) for h in HEADS}
    )
    return GstSummaryOut(period=period, outward=outward, inward_itc=itc, rcm_liability=rcm, net_payable=net,
                         voucher_count=len(docs))  # fmt: skip


# ================================================================= validation
async def validate(db: AsyncSession, ctx: TenantContext, period: str, docs: list[Doc] | None = None
                   ) -> list[GstValidationIssue]:  # fmt: skip
    start, end = _month(period)
    org = await _org(db, ctx)
    docs = docs if docs is not None else await _docs(db, ctx, start, end, OUTWARD + INWARD)
    slabs = (await get_config(db, "GST_SLABS", on_date=end)).get("rates", [])
    issues: list[GstValidationIssue] = []

    def add(d: Doc | None, sev: str, code: str, msg: str) -> None:
        issues.append(GstValidationIssue(voucher_id=d.v.id if d else None, voucher_number=d.v.voucher_number if d else None,
                                         severity=sev, code=code, message=msg))  # fmt: skip

    if org.gst_reg_type == "REGULAR" and not is_valid_gstin(org.gstin):
        add(None, "ERROR", "INVALID_GSTIN", f"Organization GSTIN {org.gstin or '-'} is missing or fails the checksum")
    for d in docs:
        pd = d.v.party.party_details if d.v.party else {}
        if d.v.party is None:
            add(d, "WARNING", "MISSING_PARTY", "No party ledger on the voucher")
        if d.gstin and not is_valid_gstin(d.gstin):
            add(d, "ERROR", "INVALID_GSTIN", f"Party GSTIN {d.gstin} fails the format/checksum test")
        if not d.gstin and d.v.party and not pd.get("is_unregistered") and not d.export:
            sev = "ERROR" if d.v.base_type in INWARD and sum(d.tax.values(), ZERO) else "WARNING"
            add(d, sev, "MISSING_GSTIN", f"{d.v.party.name} has no GSTIN (treated as unregistered / B2C)")
        if d.gstin and pd.get("state_code") and d.gstin[:2] != pd["state_code"]:
            add(d, "WARNING", "POS_MISMATCH", f"Party state {pd['state_code']} differs from GSTIN state {d.gstin[:2]}")
        intra_posted = d.tax["cgst"] + d.tax["sgst"] > 0
        if (d.inter and intra_posted) or (not d.inter and d.tax["igst"] > 0):
            add(
                d,
                "ERROR",
                "POS_MISMATCH",
                f"Tax split does not match place of supply {d.pos} ({'inter' if d.inter else 'intra'}-state)",
            )
        for r in d.rows:
            if slabs and not rate_in_slabs(r["rate"], slabs):
                add(d, "ERROR", "RATE_NOT_IN_SLAB", f"GST rate {to_str(r['rate'])}% is not a notified slab")
            if d.v.base_type in OUTWARD and not r["hsn"]:
                add(d, "WARNING", "MISSING_HSN", "HSN/SAC code missing on a line")
        breakup_tax = sum((r[h] for r in d.rows for h in HEADS), ZERO)
        posted = sum(d.tax.values(), ZERO) or d.rcm
        if abs(breakup_tax - posted) > 1:
            add(
                d,
                "WARNING",
                "TAX_MISMATCH",
                f"Posted tax {to_str(posted)} differs from the rate breakup {to_str(breakup_tax)}",
            )
    return issues


# ================================================================= GSTR-1
def _itm(r: dict[str, Any], sign: Decimal, n: int) -> dict[str, Any]:
    return {"num": n, "itm_det": {"txval": q2(sign * r["taxable"]), "rt": r["rate"], "iamt": q2(sign * r["igst"]),
                                  "camt": q2(sign * r["cgst"]), "samt": q2(sign * r["sgst"]), "csamt": q2(sign * r["cess"])}}  # fmt: skip


def _inv(d: Doc, num_key: str = "inum", date_key: str = "idt") -> dict[str, Any]:
    return {num_key: d.v.voucher_number, date_key: _gstn_date(d.v.voucher_date), "val": q2(d.value), "pos": d.pos,
            "itms": [_itm(r, Decimal(1), i + 1) for i, r in enumerate(d.rows)]}  # fmt: skip


async def _gstr1_struct(
    db: AsyncSession, ctx: TenantContext, period: str
) -> tuple[dict[str, Any], list[Doc], OrgBrief]:
    start, end = _month(period)
    org = await _org(db, ctx)
    cfg = await get_config(db, "GST_SLABS", on_date=end)
    b2cl_limit = _d(cfg.get("b2cl_threshold", "100000"))
    aato = _d(
        (org.accounts_settings or {}).get("aato")
    )  # shortcut: AATO from accounts_settings.aato, else FY-to-date sales
    docs = await _docs(db, ctx, start, end, OUTWARD)
    if not aato:
        fy = fy_for_date(start, org.fy_begins_from)
        aato = sum((d.sign * d.taxable for d in await _docs(db, ctx, fy.start, end, OUTWARD)), ZERO)
    above_5cr = aato > Decimal("50000000")
    b2b: dict[str, list] = defaultdict(list)
    b2cl: dict[str, list] = defaultdict(list)
    b2cs: dict[tuple, dict] = {}
    cdnr: dict[str, list] = defaultdict(list)
    cdnur: list = []
    exp: dict[str, list] = defaultdict(list)
    hsn: dict[tuple, dict] = {}

    def add_b2cs(d: Doc, sign: Decimal) -> None:
        for r in d.rows:
            key = ("INTER" if d.inter else "INTRA", d.pos, r["rate"])
            row = b2cs.setdefault(key, {"sply_ty": key[0], "pos": d.pos, "typ": "OE", "rt": r["rate"], "txval": ZERO,
                                        "iamt": ZERO, "camt": ZERO, "samt": ZERO, "csamt": ZERO})  # fmt: skip
            for k, src in (
                ("txval", "taxable"),
                ("iamt", "igst"),
                ("camt", "cgst"),
                ("samt", "sgst"),
                ("csamt", "cess"),
            ):
                row[k] += sign * r[src]

    for d in docs:
        note = d.v.base_type == "CREDIT_NOTE"
        exp_typ = "WPAY" if d.tax["igst"] > 0 else "WOPAY"
        if d.export:
            if note:
                cdnur.append({"typ": f"EXP{exp_typ}", "ntty": "C", **_inv(d, "nt_num", "nt_dt")})
            else:
                exp[exp_typ].append({"inum": d.v.voucher_number, "idt": _gstn_date(d.v.voucher_date), "val": q2(d.value),
                                     "sbpcode": None, "sbnum": None, "sbdt": None,
                                     "itms": [{"txval": q2(r["taxable"]), "rt": r["rate"], "iamt": q2(r["igst"]),
                                               "csamt": q2(r["cess"])} for r in d.rows]})  # fmt: skip
        elif d.gstin:
            inv_typ = ("SEWP" if d.tax["igst"] > 0 else "SEWOP") if d.sez else "R"
            body = {
                **_inv(d, "nt_num" if note else "inum", "nt_dt" if note else "idt"),
                "rchrg": "N",
                "inv_typ": inv_typ,
            }
            (cdnr[d.gstin].append({"ntty": "C", **body}) if note else b2b[d.gstin].append(body))
        elif d.inter and d.value > b2cl_limit:
            (cdnur.append({"typ": "B2CL", "ntty": "C", **_inv(d, "nt_num", "nt_dt")}) if note
             else b2cl[d.pos].append({k: v for k, v in _inv(d).items() if k != "pos"}))  # fmt: skip
        else:
            add_b2cs(d, d.sign)
        for r in d.rows:
            code = hsn_for_return(r["hsn"], above_5cr=above_5cr) or "NA"
            key = (code, r["rate"])
            h = hsn.setdefault(key, {"hsn_sc": code, "desc": "", "uqc": (r["uom"] or "OTH").upper()[:3], "qty": ZERO,
                                     "rt": r["rate"], "txval": ZERO, "iamt": ZERO, "camt": ZERO, "samt": ZERO, "csamt": ZERO})  # fmt: skip
            h["qty"] += d.sign * r["qty"]
            for k, src in (
                ("txval", "taxable"),
                ("iamt", "igst"),
                ("camt", "cgst"),
                ("samt", "sgst"),
                ("csamt", "cess"),
            ):
                h[k] += d.sign * r[src]
    struct = {
        "b2b": [{"ctin": k, "inv": v} for k, v in sorted(b2b.items())],
        "b2cl": [{"pos": k, "inv": v} for k, v in sorted(b2cl.items())],
        "b2cs": list(b2cs.values()),
        "cdnr": [{"ctin": k, "nt": v} for k, v in sorted(cdnr.items())],
        "cdnur": cdnur,
        "exp": [{"exp_typ": k, "inv": v} for k, v in sorted(exp.items())],
        "hsn": [{"num": i + 1, **h} for i, h in enumerate(hsn.values())],
    }
    return struct, docs, org


async def gstr1(db: AsyncSession, ctx: TenantContext, period: str) -> Gstr1Out:
    struct, docs, org = await _gstr1_struct(db, ctx, period)
    return Gstr1Out(period=period, gstin=org.gstin, totals=_totals(docs), errors=await validate(db, ctx, period, docs),
                    **{k: to_jsonable(v) for k, v in struct.items()})  # fmt: skip


def gstn_dumps(obj: Any) -> str:
    """JSON with Decimal rendered as plain numbers (GSTN offline-tool format) — never via float."""
    if isinstance(obj, Decimal):
        return format(q2(obj), "f")
    if isinstance(obj, dict):
        return "{" + ",".join(f"{json.dumps(str(k))}:{gstn_dumps(v)}" for k, v in obj.items()) + "}"
    if isinstance(obj, (list, tuple)):
        return "[" + ",".join(gstn_dumps(v) for v in obj) + "]"
    return json.dumps(to_jsonable(obj))


def _fp(period: str) -> str:
    y, m = period.split("-")
    return f"{m}{y}"


async def gstr1_export(db: AsyncSession, ctx: TenantContext, period: str) -> tuple[bytes, str]:
    struct, _docs_, org = await _gstr1_struct(db, ctx, period)
    payload = {"gstin": org.gstin, "fp": _fp(period), "version": "GST3.1.6", "hash": "hash",
               **{k: v for k, v in struct.items() if k != "hsn"}, "hsn": {"data": struct["hsn"]}}  # fmt: skip
    await write_audit(db, ctx, M, "EXPORT", "gstr1", ctx.org_id, after={"period": period})
    return gstn_dumps(payload).encode(), f"GSTR1_{org.gstin or 'NA'}_{_fp(period)}.json"


# ================================================================= GSTR-3B
def _heads(t: dict[str, Decimal]) -> dict[str, Decimal]:
    return {"txval": q2(t.get("txval", ZERO)), "iamt": q2(t["iamt"]), "camt": q2(t["camt"]), "samt": q2(t["samt"]),
            "csamt": q2(t["csamt"])}  # fmt: skip


def _zero() -> dict[str, Decimal]:
    return {"txval": ZERO, "iamt": ZERO, "camt": ZERO, "samt": ZERO, "csamt": ZERO}


def _acc(t: dict[str, Decimal], d: Doc, *, tax: dict[str, Decimal] | None = None) -> None:
    tax = tax or d.tax
    t["txval"] += d.sign * d.taxable
    for k, h in (("iamt", "igst"), ("camt", "cgst"), ("samt", "sgst"), ("csamt", "cess")):
        t[k] += d.sign * tax[h]


def set_off(liability: dict[str, Decimal], credit: dict[str, Decimal]) -> dict[str, Any]:
    """Rule 88A order: IGST credit -> IGST, CGST, SGST; CGST credit -> CGST, IGST; SGST credit -> SGST, IGST.
    Cess credit only against cess."""
    due = {h: max(liability.get(h, ZERO), ZERO) for h in HEADS}
    left = {h: max(credit.get(h, ZERO), ZERO) for h in HEADS}
    used: dict[str, dict[str, Decimal]] = {h: dict.fromkeys(HEADS, ZERO) for h in HEADS}
    order = {"igst": ("igst", "cgst", "sgst"), "cgst": ("cgst", "igst"), "sgst": ("sgst", "igst"), "cess": ("cess",)}
    for src in ("igst", "cgst", "sgst", "cess"):
        for dst in order[src]:
            take = min(left[src], due[dst])
            left[src] -= take
            due[dst] -= take
            used[src][dst] += take
    return {"tax_payable": {h: q2(max(liability.get(h, ZERO), ZERO)) for h in HEADS},
            "itc_utilised": {s: {d: q2(v) for d, v in m.items()} for s, m in used.items()},
            "cash_payable": {h: q2(v) for h, v in due.items()}, "itc_carry_forward": {h: q2(v) for h, v in left.items()}}  # fmt: skip


async def _gstr3b_struct(db: AsyncSession, ctx: TenantContext, period: str) -> dict[str, Any]:
    start, end = _month(period)
    org = await _org(db, ctx)
    docs = await _docs(db, ctx, start, end, OUTWARD + INWARD)
    osup_det, osup_zero, osup_nil, isup_rev = _zero(), _zero(), _zero(), _zero()
    unreg: dict[str, dict[str, Decimal]] = defaultdict(lambda: {"txval": ZERO, "iamt": ZERO})
    itc_oth, itc_rcm = _zero(), _zero()
    exempt_in = {"inter": ZERO, "intra": ZERO}
    for d in docs:
        tax_total = sum(d.tax.values(), ZERO)
        if d.v.base_type in OUTWARD:
            if d.export or d.sez:
                _acc(osup_zero, d)
            elif tax_total == 0:
                osup_nil["txval"] += d.sign * d.taxable
            else:
                _acc(osup_det, d)
                if not d.gstin and d.inter:
                    unreg[d.pos]["txval"] += d.sign * d.taxable
                    unreg[d.pos]["iamt"] += d.sign * d.tax["igst"]
        else:
            if d.reverse_charge:
                rcm = {"igst": d.rcm if d.inter else ZERO, "cgst": ZERO if d.inter else q2(d.rcm / 2),
                       "sgst": ZERO if d.inter else d.rcm - q2(d.rcm / 2), "cess": ZERO}  # fmt: skip
                _acc(isup_rev, d, tax=rcm)
                _acc(itc_rcm, d)
            elif tax_total == 0:
                exempt_in["inter" if d.inter else "intra"] += d.sign * d.taxable
            else:
                _acc(itc_oth, d)
    zero = {"iamt": ZERO, "camt": ZERO, "samt": ZERO, "csamt": ZERO}
    avl = [{"ty": "IMPG", **zero}, {"ty": "IMPS", **zero}, {"ty": "ISRC", **{k: q2(itc_rcm[k]) for k in zero}},
           {"ty": "ISD", **zero}, {"ty": "OTH", **{k: q2(itc_oth[k]) for k in zero}}]  # fmt: skip
    net = {k: q2(itc_rcm[k] + itc_oth[k]) for k in zero}
    liability = {"igst": osup_det["iamt"] + osup_zero["iamt"] + isup_rev["iamt"],
                 "cgst": osup_det["camt"] + isup_rev["camt"], "sgst": osup_det["samt"] + isup_rev["samt"],
                 "cess": osup_det["csamt"] + osup_zero["csamt"] + isup_rev["csamt"]}  # fmt: skip
    rcm_cash = {"igst": isup_rev["iamt"], "cgst": isup_rev["camt"], "sgst": isup_rev["samt"], "cess": isup_rev["csamt"]}
    payment = set_off({h: liability[h] - rcm_cash[h] for h in HEADS},
                      {"igst": net["iamt"], "cgst": net["camt"], "sgst": net["samt"], "cess": net["csamt"]})  # fmt: skip
    payment["rcm_cash_payable"] = {h: q2(v) for h, v in rcm_cash.items()}
    payment["tax_payable"] = {h: q2(liability[h]) for h in HEADS}
    return {
        "gstin": org.gstin,
        "sec_3_1": {"osup_det": _heads(osup_det), "osup_zero": _heads(osup_zero),
                    "osup_nil_exmp": {"txval": q2(osup_nil["txval"])}, "isup_rev": _heads(isup_rev),
                    "osup_nongst": {"txval": ZERO}},
        "sec_3_2": {"unreg_details": [{"pos": k, "txval": q2(v["txval"]), "iamt": q2(v["iamt"])} for k, v in sorted(unreg.items())],
                    "comp_details": [], "uin_details": []},
        "sec_4": {"itc_avl": avl, "itc_rev": [{"ty": "RUL", **zero}, {"ty": "OTH", **zero}], "itc_net": net,
                  "itc_inelg": [{"ty": "RUL", **zero}, {"ty": "OTH", **zero}]},
        "sec_5": {"isup_details": [{"ty": "GST", "inter": q2(exempt_in["inter"]), "intra": q2(exempt_in["intra"])},
                                   {"ty": "NONGST", "inter": ZERO, "intra": ZERO}]},
        "sec_6_1": payment,
    }  # fmt: skip


async def gstr3b(db: AsyncSession, ctx: TenantContext, period: str) -> Gstr3bOut:
    s = await _gstr3b_struct(db, ctx, period)
    return Gstr3bOut(
        period=period, **{k: to_jsonable(s[k]) for k in ("sec_3_1", "sec_3_2", "sec_4", "sec_5", "sec_6_1")}
    )


async def gstr3b_export(db: AsyncSession, ctx: TenantContext, period: str) -> tuple[bytes, str]:
    s = await _gstr3b_struct(db, ctx, period)
    payload = {"gstin": s["gstin"], "ret_period": _fp(period), "sup_details": s["sec_3_1"], "inter_sup": s["sec_3_2"],
               "itc_elg": s["sec_4"], "inward_sup": s["sec_5"], "tax_pmt": s["sec_6_1"]}  # fmt: skip
    await write_audit(db, ctx, M, "EXPORT", "gstr3b", ctx.org_id, after={"period": period})
    return gstn_dumps(payload).encode(), f"GSTR3B_{s['gstin'] or 'NA'}_{_fp(period)}.json"


# ================================================================= GSTR-2B
def _norm_inv(s: str | None) -> str:
    return re.sub(r"[^A-Z0-9]", "", (s or "").upper()).lstrip("0")


def _parse_gstn_date(s: str | None) -> date | None:
    for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(s), fmt).date()
        except (ValueError, TypeError):
            continue
    return None


def parse_2b(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """GSTR-2B (``data.docdata.b2b[].inv[].items[]``) or GSTR-2A style (``b2b[].inv[].itms[].itm_det``) -> invoices."""
    root = payload.get("data", payload)
    docdata = root.get("docdata", root)
    out: list[dict[str, Any]] = []
    for section, key, sign in (("b2b", "inv", 1), ("cdnr", "nt", -1)):
        for sup in docdata.get(section) or []:
            for inv in sup.get(key) or sup.get("inv") or []:
                taxable = tax = ZERO
                for it in inv.get("items") or inv.get("itms") or []:
                    det = it.get("itm_det", it)
                    taxable += _d(det.get("txval"))
                    tax += sum(
                        (_d(det.get(k)) for k in ("igst", "cgst", "sgst", "cess", "iamt", "camt", "samt", "csamt")),
                        ZERO,
                    )
                d = _parse_gstn_date(inv.get("dt") or inv.get("idt") or inv.get("nt_dt"))
                number = inv.get("inum") or inv.get("ntnum") or inv.get("nt_num")
                if not sup.get("ctin") or not number or d is None:
                    continue
                out.append({"gstin": str(sup["ctin"]).upper(), "supplier_name": sup.get("trdnm"), "invoice_no": str(number),
                            "invoice_date": d.isoformat(), "taxable": to_str(sign * taxable), "tax": to_str(sign * tax)})  # fmt: skip
    return out


async def import_2b(db: AsyncSession, ctx: TenantContext, period: str, data: bytes) -> Gstr2bImportOut:
    _month(period)
    if len(data) > MAX_2B_BYTES:
        raise ValidationFailedError("GSTR-2B files are limited to 10 MB")
    try:
        payload = json.loads(data.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValidationFailedError("The file is not valid GSTR-2B JSON") from exc
    if not isinstance(payload, dict):
        raise ValidationFailedError("The file is not valid GSTR-2B JSON")
    invoices = parse_2b(payload)
    # shortcut: only the normalised invoices are stored (not the raw portal JSON); keep raw if audits need it
    row = Gst2bImport(org_id=ctx.org_id, period=period, payload={"invoices": invoices}, imported_by=ctx.user_id)
    db.add(row)
    await db.flush()
    await write_audit(
        db, ctx, M, "CREATE", "gst_2b_import", row.id, after={"period": period, "invoices": len(invoices)}
    )
    return Gstr2bImportOut(import_id=row.id, period=period, invoices=len(invoices))


async def reconcile_2b(db: AsyncSession, ctx: TenantContext, period: str) -> Gstr2bReconOut:
    start, end = _month(period)
    imp = (await db.execute(select(Gst2bImport).where(Gst2bImport.org_id == ctx.org_id, Gst2bImport.period == period)
                            .order_by(Gst2bImport.created_at.desc()).limit(1))).scalar_one_or_none()  # fmt: skip
    portal = list((imp.payload or {}).get("invoices", [])) if imp else []
    books = [d for d in await _docs(db, ctx, start, end, ("PURCHASE",)) if d.gstin]
    index: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for p in portal:
        index[(p["gstin"], _norm_inv(p["invoice_no"]))].append(p)
    out: dict[str, list[ReconRow]] = {"exact": [], "partial": [], "missing_in_books": [], "missing_in_portal": []}
    for d in books:
        inv_no = d.v.supplier_invoice_no or d.v.voucher_number
        inv_date = d.v.supplier_invoice_date or d.v.voucher_date
        tax = sum(d.tax.values(), ZERO)
        hits = index.get((d.gstin, _norm_inv(inv_no)))
        row = {"gstin": d.gstin, "supplier_name": d.v.party.name if d.v.party else None, "invoice_no": inv_no,
               "invoice_date": inv_date, "taxable": d.taxable, "tax": tax, "voucher_id": d.v.id}  # fmt: skip
        if not hits:
            out["missing_in_portal"].append(ReconRow(**row, portal_taxable=None, portal_tax=None, difference=None))
            continue
        p = hits.pop(0)
        pt, ptax = _d(p["taxable"]), _d(p["tax"])
        ok = (
            abs((date.fromisoformat(p["invoice_date"]) - inv_date).days) <= 1
            and abs(ptax - tax) <= 1
            and abs(pt - d.taxable) <= 1
        )
        out["exact" if ok else "partial"].append(
            ReconRow(**row, portal_taxable=pt, portal_tax=ptax, difference=tax - ptax)
        )
    for rest in index.values():
        for p in rest:
            out["missing_in_books"].append(ReconRow(
                gstin=p["gstin"], supplier_name=p.get("supplier_name"), invoice_no=p["invoice_no"],
                invoice_date=date.fromisoformat(p["invoice_date"]), taxable=_d(p["taxable"]), tax=_d(p["tax"]),
                voucher_id=None, portal_taxable=_d(p["taxable"]), portal_tax=_d(p["tax"]), difference=None))  # fmt: skip
    return Gstr2bReconOut(period=period, **out)


# ================================================================= e-invoice / e-way bill
def _rec_out(r: EinvoiceRecord) -> EinvoiceOut:
    return EinvoiceOut(voucher_id=r.voucher_id, kind=r.kind, status=r.status, irn=r.irn, ack_no=r.ack_no,
                       ack_date=r.ack_date, signed_qr=r.signed_qr, eway_bill_no=r.eway_bill_no, valid_until=r.valid_until)  # fmt: skip


async def list_einvoice(db: AsyncSession, ctx: TenantContext, voucher_id: uuid.UUID) -> list[EinvoiceOut]:
    await accounts.get_voucher_full(db, ctx, voucher_id)
    rows = (await db.execute(select(EinvoiceRecord).where(EinvoiceRecord.org_id == ctx.org_id,
                                                          EinvoiceRecord.voucher_id == voucher_id)
                             .order_by(EinvoiceRecord.created_at))).scalars()  # fmt: skip
    return [_rec_out(r) for r in rows]


async def _active(db: AsyncSession, ctx: TenantContext, voucher_id: uuid.UUID, kind: str) -> EinvoiceRecord | None:
    return (await db.execute(select(EinvoiceRecord).where(
        EinvoiceRecord.org_id == ctx.org_id, EinvoiceRecord.voucher_id == voucher_id, EinvoiceRecord.kind == kind,
        EinvoiceRecord.status == "GENERATED"))).scalar_one_or_none()  # fmt: skip


def _irn_payload(org: OrgBrief, d: Doc) -> dict[str, Any]:
    pd = d.v.party.party_details if d.v.party else {}
    typ = {"SALES": "INV", "CREDIT_NOTE": "CRN", "DEBIT_NOTE": "DBN"}[d.v.base_type]
    return to_jsonable({
        "Version": "1.1",
        "TranDtls": {"TaxSch": "GST", "SupTyp": ("EXPWP" if d.tax["igst"] else "EXPWOP") if d.export else
                     ("SEZWP" if d.tax["igst"] else "SEZWOP") if d.sez else "B2B", "RegRev": "N"},
        "DocDtls": {"Typ": typ, "No": d.v.voucher_number, "Dt": d.v.voucher_date.strftime("%d/%m/%Y")},
        "SellerDtls": {"Gstin": org.gstin, "LglNm": org.legal_name, "Addr1": (org.address_lines or [""])[0],
                       "Stcd": org.state_code},
        "BuyerDtls": {"Gstin": d.gstin or "URP", "LglNm": d.v.party.name if d.v.party else "", "Pos": d.pos,
                      "Addr1": pd.get("address") or "", "Stcd": pd.get("state_code") or d.pos},
        "ItemList": [{"SlNo": str(i + 1), "HsnCd": r["hsn"] or "", "Qty": r["qty"], "Unit": (r["uom"] or "OTH").upper()[:3],
                      "AssAmt": r["taxable"], "GstRt": r["rate"], "IgstAmt": r["igst"], "CgstAmt": r["cgst"],
                      "SgstAmt": r["sgst"], "CesAmt": r["cess"]} for i, r in enumerate(d.rows)],
        "ValDtls": {"AssVal": d.taxable, "CgstVal": d.tax["cgst"], "SgstVal": d.tax["sgst"], "IgstVal": d.tax["igst"],
                    "CesVal": d.tax["cess"], "TotInvVal": d.v.total_amount},
    })  # fmt: skip


async def generate_einvoice(db: AsyncSession, ctx: TenantContext, voucher_id: uuid.UUID) -> EinvoiceOut:
    v = await accounts.get_voucher_full(db, ctx, voucher_id)
    if v.base_type not in ("SALES", "CREDIT_NOTE", "DEBIT_NOTE"):
        raise ValidationFailedError("e-Invoices are generated for sales invoices and credit/debit notes")
    if v.status != "REGULAR":
        raise InvalidStateError("Only regular vouchers can be e-invoiced")
    org = await _org(db, ctx)
    d = _doc(v, org)
    if not is_valid_gstin(org.gstin):
        raise ValidationFailedError("The organization GSTIN is missing or invalid")
    if not d.export and not (d.gstin and is_valid_gstin(d.gstin)):
        raise ValidationFailedError("e-Invoicing needs a registered buyer (valid GSTIN) or an export invoice")
    if await _active(db, ctx, v.id, "IRN"):
        raise AlreadyExistsError("An active IRN already exists for this voucher")
    res = await get_tax_gateway().generate_irn(_irn_payload(org, d))
    rec = EinvoiceRecord(org_id=ctx.org_id, voucher_id=v.id, kind="IRN", status="GENERATED", irn=res.irn,
                         ack_no=res.ack_no, ack_date=res.ack_date, signed_qr=res.signed_qr, raw=to_jsonable(res.raw))  # fmt: skip
    db.add(rec)
    await db.flush()
    await accounts.update_voucher_gst_metadata(db, ctx, v.id, {"einvoice": {"irn": res.irn, "ack_no": res.ack_no,
                                               "ack_date": res.ack_date, "status": "GENERATED"}})  # fmt: skip
    await write_audit(db, ctx, M, "CREATE", "einvoice", rec.id, after={"voucher_id": v.id, "irn": res.irn})
    return _rec_out(rec)


async def cancel_einvoice(db: AsyncSession, ctx: TenantContext, voucher_id: uuid.UUID, body: EinvoiceCancelIn
                          ) -> EinvoiceOut:  # fmt: skip
    await accounts.get_voucher_full(db, ctx, voucher_id)
    rec = await _active(db, ctx, voucher_id, "IRN")
    if rec is None:
        raise InvalidStateError("There is no active IRN to cancel")
    # shortcut: the IRP 24-hour cancellation window is enforced by the live gateway, not here (Mock ack dates are fixed)
    raw = await get_tax_gateway().cancel_irn(rec.irn or "", body.reason_code, body.remarks)
    rec.status, rec.raw = "CANCELLED", {**(rec.raw or {}), "cancel": to_jsonable(raw)}
    await db.flush()
    await accounts.update_voucher_gst_metadata(db, ctx, voucher_id, {"einvoice": {"irn": rec.irn, "status": "CANCELLED",
                                               "cancel_reason": body.reason_code}})  # fmt: skip
    await write_audit(db, ctx, M, "CANCEL", "einvoice", rec.id, after={"irn": rec.irn}, reason=body.remarks)
    return _rec_out(rec)


async def generate_eway(db: AsyncSession, ctx: TenantContext, voucher_id: uuid.UUID, body: EwayBillIn) -> EinvoiceOut:
    v = await accounts.get_voucher_full(db, ctx, voucher_id)
    if v.status != "REGULAR":
        raise InvalidStateError("Only regular vouchers can carry an e-way bill")
    if not v.inventory:
        raise ValidationFailedError("e-Way bills are for movement of goods: the voucher has no stock lines")
    if body.transport_mode == "ROAD" and not (body.vehicle_no or body.transporter_id):
        raise ValidationFailedError("Road transport needs a vehicle number or a transporter id")
    if await _active(db, ctx, v.id, "EWAY"):
        raise AlreadyExistsError("An active e-way bill already exists for this voucher")
    org = await _org(db, ctx)
    d = _doc(v, org)
    outward = v.base_type not in ("PURCHASE", "RECEIPT_NOTE")
    payload = to_jsonable({"supplyType": "O" if outward else "I", "docType": "INV", "docNo": v.voucher_number,
                           "docDate": v.voucher_date.strftime("%d/%m/%Y"), "fromGstin": org.gstin if outward else d.gstin,
                           "toGstin": (d.gstin or "URP") if outward else org.gstin, "totValue": v.total_amount,
                           "transMode": body.transport_mode, "distance_km": body.distance_km,
                           "vehicleNo": body.vehicle_no, "transporterId": body.transporter_id,
                           "transporterName": body.transporter_name,
                           "itemList": [{"hsnCode": i["hsn"], "quantity": i["quantity"], "taxableAmount": i["amount"]}
                                        for i in v.inventory]})  # fmt: skip
    res = await get_tax_gateway().generate_eway_bill(payload)
    rec = EinvoiceRecord(org_id=ctx.org_id, voucher_id=v.id, kind="EWAY", status="GENERATED",
                         eway_bill_no=res.eway_bill_no, valid_until=res.valid_until, raw=to_jsonable(res.raw))  # fmt: skip
    db.add(rec)
    await db.flush()
    await accounts.update_voucher_gst_metadata(db, ctx, v.id, {"eway_bill": {"number": res.eway_bill_no,
                                               "valid_until": res.valid_until}})  # fmt: skip
    await write_audit(db, ctx, M, "CREATE", "eway_bill", rec.id, after={"voucher_id": v.id, "number": res.eway_bill_no})
    return _rec_out(rec)


# ================================================================= TDS / TCS
async def _tds_cfg(db: AsyncSession, on: date | None) -> dict[str, Any]:
    return await get_config(db, "TDS_SECTIONS", on_date=on)


async def tds_sections(db: AsyncSession, ctx: TenantContext, on_date: date | None) -> list[TdsSectionOut]:
    return [TdsSectionOut(section=s["section"], nature=s["nature"], threshold_single=s.get("threshold_single"),
                          threshold_annual=s.get("threshold_annual"), rate_individual=s["rate_individual"],
                          rate_company=s["rate_company"], rate_no_pan=s["rate_no_pan"])
            for s in (await _tds_cfg(db, on_date))["sections"]]  # fmt: skip


async def tds_compute(db: AsyncSession, ctx: TenantContext, body: TdsComputeIn) -> TdsComputeOut:
    cfg = next((s for s in (await _tds_cfg(db, body.voucher_date))["sections"] if s["section"] == body.section), None)
    if cfg is None:
        raise ValidationFailedError(f"Unknown TDS/TCS section {body.section}")
    party = await accounts.get_ledger(db, ctx, body.party_ledger_id)
    org = await _org(db, ctx)
    fy = fy_for_date(body.voucher_date, org.fy_begins_from)
    ytd = ZERO
    if body.voucher_date > fy.start:
        # shortcut: FY aggregate = party vouchers' expense DRs (TDS) / income CRs (TCS); per-section tagging when ledgers carry tds_section
        tcs = cfg.get("kind") == "TCS"
        for v in await accounts.list_vouchers_full(db, ctx, date_from=fy.start, date_to=body.voucher_date - timedelta(days=1),
                                                   party_ledger_id=party.id):  # fmt: skip
            for e in v.entries:
                tagged = (e["tax_config"] or {}).get("tds_section")
                if tagged and tagged != body.section:
                    continue
                if (tcs and e["nature"] == "INCOME" and e["entry_type"] == "CR") or (
                        not tcs and e["nature"] == "EXPENSES" and e["entry_type"] == "DR"):  # fmt: skip
                    ytd += e["amount"]
    r = compute_tds(cfg, amount=body.amount, ytd=ytd, pan=party.party_details.get("pan"),
                    deductee_type=party.party_details.get("deductee_type"))  # fmt: skip
    return TdsComputeOut(applicable=r.applicable, section=r.section, rate=r.rate, tds_amount=r.tds_amount,
                         threshold_info=r.threshold_info, pan_available=r.pan_available)  # fmt: skip


@dataclass
class Deduction:
    voucher: VoucherFullDTO
    section: str
    kind: str
    amount_paid: Decimal
    tds: Decimal


def _is_tds_ledger(e: dict[str, Any]) -> bool:
    tc = e["tax_config"] or {}
    return (
        str(tc.get("tax_type", "")).upper() in ("TDS", "TCS")
        and not e["is_party"]
        and e["system_code"] != "SALARY_TDS_PAYABLE"
        and tc.get("tds_section") != "192"
    )  # party tax_config = deductee tag


async def _deductions(db: AsyncSession, ctx: TenantContext, start: date, end: date) -> tuple[list[Deduction], dict]:
    cfg = {s["section"]: s for s in (await _tds_cfg(db, end))["sections"]}
    out: list[Deduction] = []
    for v in await accounts.list_vouchers_full(db, ctx, date_from=start, date_to=end):
        tds_lines = [e for e in v.entries if _is_tds_ledger(e) and e["entry_type"] == "CR"]
        if not tds_lines or v.party is None:
            continue
        for e in tds_lines:
            tagged = (e["tax_config"] or {}).get("tds_section")
            exp_tag = next(((x["tax_config"] or {}).get("tds_section") for x in v.entries
                            if x["nature"] in ("EXPENSES", "INCOME") and (x["tax_config"] or {}).get("tds_section")), None)  # fmt: skip
            section = tagged or exp_tag or (v.party.tax_config or {}).get("tds_section") or "UNSPECIFIED"
            kind = (
                "TCS"
                if str((e["tax_config"] or {}).get("tax_type")).upper() == "TCS" or section.startswith("206C")
                else "TDS"
            )
            nature, side = ("INCOME", "CR") if kind == "TCS" else ("EXPENSES", "DR")
            paid = sum((x["amount"] for x in v.entries if x["nature"] == nature and x["entry_type"] == side), ZERO)
            out.append(Deduction(v, section, kind, paid, e["amount"]))
    return out, cfg


async def tds_summary(db: AsyncSession, ctx: TenantContext, date_from: date, date_to: date) -> list[TdsSummaryRow]:
    if date_from > date_to:
        raise ValidationFailedError("date_from must be on or before date_to")
    deds, _ = await _deductions(db, ctx, date_from, date_to)
    cfg = await _tds_cfg(db, date_to)
    org = await _org(db, ctx)
    # deposits: DR on TDS/TCS ledgers (challan payments) from the start of the FY
    fy = fy_for_date(date_from, org.fy_begins_from)
    all_vs = await accounts.list_vouchers_full(db, ctx, date_from=fy.start, date_to=None)
    deposits = sorted((v.voucher_date, e["amount"]) for v in all_vs for e in v.entries
                      if _is_tds_ledger(e) and e["entry_type"] == "DR")  # fmt: skip
    deducted_all = sorted((v.voucher_date, e["amount"]) for v in all_vs for e in v.entries
                          if _is_tds_ledger(e) and e["entry_type"] == "CR")  # fmt: skip

    def month_ok(m: date) -> bool:
        due = challan_due_date(m, cfg)
        need = sum((a for d, a in deducted_all if d <= month_end(m)), ZERO)
        paid = sum((a for d, a in deposits if d <= due), ZERO)
        return paid >= need

    rows: dict[tuple[str, uuid.UUID], dict[str, Any]] = {}
    for dd in deds:
        p = dd.voucher.party
        key = (dd.section, p.id)
        r = rows.setdefault(key, {"section": dd.section, "party_ledger_id": p.id, "party_name": p.name,
                                  "pan": p.party_details.get("pan"), "amount_paid": ZERO, "tds_amount": ZERO,
                                  "deposited": True})  # fmt: skip
        r["amount_paid"] += dd.amount_paid
        r["tds_amount"] += dd.tds
        r["deposited"] = r["deposited"] and month_ok(dd.voucher.voucher_date.replace(day=1))
    return [TdsSummaryRow(**r) for r in sorted(rows.values(), key=lambda r: (r["section"], r["party_name"]))]


async def tds_challan(db: AsyncSession, ctx: TenantContext, month: str) -> TdsChallanOut:
    start, end = _month(month)
    deds, cfg = await _deductions(db, ctx, start, end)
    by: dict[str, dict[str, Any]] = {}
    for dd in deds:
        s = by.setdefault(dd.section, {"section": dd.section, "nature": (cfg.get(dd.section) or {}).get("nature", ""),
                                       "kind": dd.kind, "amount": ZERO, "deductees": set(), "challan": "ITNS 281",
                                       "minor_head": "200"})  # fmt: skip
        s["amount"] += dd.tds
        s["deductees"].add(dd.voucher.party.id)
    rows = [{**s, "amount": to_str(s["amount"]), "deductees": len(s["deductees"])} for s in by.values()]
    total = sum((dd.tds for dd in deds), ZERO)
    return TdsChallanOut(month=month, due_date=challan_due_date(start, await _tds_cfg(db, end)), by_section=rows,
                         total=total)  # fmt: skip


async def tds_return_file(db: AsyncSession, ctx: TenantContext, form: str, quarter: str) -> tuple[bytes, str]:
    """Pipe-delimited text approximating the NSDL FVU layout (FH / BH / CD / DD records).

    shortcut: approximate layout for review and hand-off to a return-preparation utility; not FVU-validated.
    """
    form = form.upper()
    if form not in ("26Q", "27Q", "27EQ"):
        raise ValidationFailedError("form must be 26Q, 27Q or 27EQ")
    try:
        start, end = fy_quarter(quarter)
    except ValueError as exc:
        raise ValidationFailedError(str(exc)) from exc
    org = await _org(db, ctx)
    deds, _cfg = await _deductions(db, ctx, start, end)

    def keep(dd: Deduction) -> bool:
        nri = (
            dd.voucher.party.party_details.get("deductee_type") or ""
        ).upper() == "NON_RESIDENT" or dd.section == "195"
        return dd.kind == "TCS" if form == "27EQ" else (dd.kind == "TDS" and (nri if form == "27Q" else not nri))

    deds = [dd for dd in deds if keep(dd)]
    months: dict[date, list[Deduction]] = defaultdict(list)
    for dd in deds:
        months[dd.voucher.voucher_date.replace(day=1)].append(dd)
    fy = fy_for_date(start, org.fy_begins_from)
    today = datetime.now(UTC).strftime("%d%m%Y")
    lines = [f"FH|NS1|R|{today}|1|D|{org.tan or ''}|1|InaiFlow|||||||||",
             f"BH|1|{len(months)}|{form}|||||{org.tan or ''}||{org.pan or ''}|{fy.start.year}{fy.end.year % 100:02d}|"
             f"Q{quarter[-1]}|{org.legal_name}|{org.address_lines[0] if org.address_lines else ''}|{org.state_code}|"
             f"{org.contact_email}|{to_str(sum((d.tds for d in deds), ZERO))}"]  # fmt: skip
    for ci, (m, items) in enumerate(sorted(months.items()), start=1):
        lines.append(f"CD|1|{ci}|{len(items)}|N|||||{to_str(sum((d.tds for d in items), ZERO))}|"
                     f"{challan_due_date(m, await _tds_cfg(db, m)).strftime('%d%m%Y')}|200")  # fmt: skip
        for di, dd in enumerate(items, start=1):
            pd = dd.voucher.party.party_details
            lines.append(f"DD|1|{ci}|{di}|O|{(pd.get('pan') or 'PANNOTAVBL').upper()}|{dd.voucher.party.name}|"
                         f"{to_str(dd.amount_paid)}|{to_str(dd.tds)}|{dd.voucher.voucher_date.strftime('%d%m%Y')}|{dd.section}")  # fmt: skip
    await write_audit(
        db, ctx, M, "EXPORT", f"tds_return_{form.lower()}", ctx.org_id, after={"quarter": quarter, "rows": len(deds)}
    )
    return ("\n".join(lines) + "\n").encode(), f"{form}_{quarter}.txt"
