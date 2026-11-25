"""GST computation — pure functions (no DB). 07_ACCOUNTING_TAX_PAYROLL_RULES §2.

* Split: org (supplier) state == place of supply and not SEZ/export -> CGST + SGST (rate/2 each), else IGST.
* Tax is computed per (HSN, rate) breakup row and rounded to paise; the invoice total is rounded to the
  nearest rupee (``round_off`` = rounded - exact). Reverse charge: tax is computed but not charged to the
  party (``invoice_total`` excludes it).
* Cess: ad-valorem % (``cess_rate``) and/or specific per unit (``cess_per_unit`` x ``qty``).
"""

from __future__ import annotations

import re
from collections import OrderedDict
from dataclasses import dataclass, field
from decimal import Decimal

from app.core.money import ZERO, q2, round_rupee

GSTIN_RE = re.compile(r"^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")
_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


@dataclass(frozen=True, slots=True)
class GstContext:
    org_state: str
    pos_state: str | None
    slabs: list[str] = field(default_factory=list)
    is_sez: bool = False
    is_export: bool = False
    reverse_charge: bool = False


@dataclass(frozen=True, slots=True)
class GstLine:
    taxable: Decimal
    rate: Decimal
    hsn: str | None = None
    qty: Decimal | None = None
    cess_rate: Decimal | None = None
    cess_per_unit: Decimal | None = None
    key: object = None  # caller handle (e.g. ledger id) for grouping suggested entries


@dataclass(slots=True)
class Breakup:
    hsn: str | None
    rate: Decimal
    taxable: Decimal = ZERO
    cgst: Decimal = ZERO
    sgst: Decimal = ZERO
    igst: Decimal = ZERO
    cess: Decimal = ZERO
    qty: Decimal = ZERO


@dataclass(slots=True)
class GstResult:
    tax_split: str  # INTRA | INTER
    taxable_total: Decimal
    cgst: Decimal
    sgst: Decimal
    igst: Decimal
    cess: Decimal
    round_off: Decimal
    invoice_total: Decimal
    breakup: list[Breakup]
    warnings: list[str]

    @property
    def tax_total(self) -> Decimal:
        return self.cgst + self.sgst + self.igst + self.cess


def is_inter_state(c: GstContext) -> bool:
    return c.is_sez or c.is_export or (c.pos_state or c.org_state) != c.org_state


def place_of_supply(*, override: str | None, party_state: str | None, party_gstin: str | None, org_state: str) -> str:
    """Voucher override > party state > first two digits of the party GSTIN > org state."""
    if override:
        return override
    if party_state:
        return party_state
    if party_gstin and len(party_gstin) >= 2 and party_gstin[:2].isdigit():
        return party_gstin[:2]
    return org_state


def _norm_rate(rate: Decimal) -> str:
    text = format(rate.normalize(), "f")
    return text


def rate_in_slabs(rate: Decimal, slabs: list[str]) -> bool:
    return any(Decimal(s) == rate for s in slabs)


def compute_gst(c: GstContext, lines: list[GstLine]) -> GstResult:
    inter = is_inter_state(c)
    warnings: list[str] = []
    rows: OrderedDict[tuple[str | None, Decimal], Breakup] = OrderedDict()
    cess_by_row: dict[tuple[str | None, Decimal], Decimal] = {}
    for line in lines:
        if line.taxable < 0:
            warnings.append("Negative taxable value on a line")
        if c.slabs and not rate_in_slabs(line.rate, c.slabs):
            warnings.append(f"GST rate {_norm_rate(line.rate)}% is not a notified slab")
        key = (line.hsn or None, line.rate)
        row = rows.setdefault(key, Breakup(hsn=line.hsn or None, rate=line.rate))
        row.taxable += line.taxable
        row.qty += line.qty or ZERO
        cess = ZERO
        if line.cess_rate:
            cess += line.taxable * line.cess_rate / Decimal(100)
        if line.cess_per_unit and line.qty:
            cess += line.cess_per_unit * line.qty
        cess_by_row[key] = cess_by_row.get(key, ZERO) + cess
    for key, row in rows.items():
        if inter:
            row.igst = q2(row.taxable * row.rate / Decimal(100))
        else:
            half = q2(row.taxable * row.rate / Decimal(200))
            row.cgst = row.sgst = half
        row.cess = q2(cess_by_row.get(key, ZERO))
    taxable = sum((r.taxable for r in rows.values()), ZERO)
    cgst = sum((r.cgst for r in rows.values()), ZERO)
    sgst = sum((r.sgst for r in rows.values()), ZERO)
    igst = sum((r.igst for r in rows.values()), ZERO)
    cess = sum((r.cess for r in rows.values()), ZERO)
    exact = taxable if c.reverse_charge else taxable + cgst + sgst + igst + cess
    total = round_rupee(exact)
    return GstResult(
        tax_split="INTER" if inter else "INTRA",
        taxable_total=taxable,
        cgst=cgst,
        sgst=sgst,
        igst=igst,
        cess=cess,
        round_off=q2(total - exact),
        invoice_total=total,
        breakup=list(rows.values()),
        warnings=sorted(set(warnings)),
    )


# ---------------------------------------------------------------- GSTIN / HSN
def gstin_checksum_char(first14: str) -> str:
    total = 0
    for i, ch in enumerate(first14.upper()):
        value = _CHARS.index(ch)
        product = value * (2 if i % 2 else 1)
        total += product // 36 + product % 36
    return _CHARS[(36 - total % 36) % 36]


def is_valid_gstin(gstin: str | None) -> bool:
    if not gstin or not GSTIN_RE.match(gstin.upper()):
        return False
    return gstin_checksum_char(gstin[:14]) == gstin[14].upper()


def hsn_for_return(hsn: str | None, *, above_5cr: bool) -> str | None:
    """GSTR-1 table 12: 4 digits for AATO <= 5 Cr, 6 digits above."""
    if not hsn:
        return None
    digits = re.sub(r"\D", "", hsn)
    return digits[: 6 if above_5cr else 4] or None
