"""Pure ledger helpers: signed balances, the chart tree, outstanding bills (bill-by-bill + FIFO) and ageing.

Sign convention everywhere: DR positive, CR negative.
"""

from __future__ import annotations

import uuid
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from app.core.money import ZERO


def signed(entry_type: str, amount: Decimal) -> Decimal:
    return amount if entry_type == "DR" else -amount


def split(value: Decimal) -> tuple[Decimal, str]:
    """Signed balance -> (absolute amount, DR|CR)."""
    return (value, "DR") if value >= 0 else (-value, "CR")


def opening_signed(amount: Decimal | None, kind: str | None) -> Decimal:
    amount = amount or ZERO
    return amount if (kind or "DR") == "DR" else -amount


# ---------------------------------------------------------------- chart
@dataclass(frozen=True, slots=True)
class GroupNode:
    id: uuid.UUID
    name: str
    parent_id: uuid.UUID | None
    nature: str
    affects_gross_profit: bool
    system_code: str | None
    is_system: bool


@dataclass(frozen=True, slots=True)
class LedgerNode:
    id: uuid.UUID
    name: str
    group_id: uuid.UUID
    system_code: str | None
    opening: Decimal  # signed
    is_active: bool
    party_details: dict[str, Any]
    tax_config: dict[str, Any] | None
    default_credit_days: int | None
    maintain_bill_by_bill: bool


@dataclass
class Chart:
    groups: dict[uuid.UUID, GroupNode]
    ledgers: dict[uuid.UUID, LedgerNode]
    children: dict[uuid.UUID | None, list[uuid.UUID]] = field(default_factory=dict)
    by_code: dict[str, uuid.UUID] = field(default_factory=dict)
    ledger_by_code: dict[str, uuid.UUID] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for g in sorted(self.groups.values(), key=lambda g: g.name):
            self.children.setdefault(g.parent_id, []).append(g.id)
            if g.system_code:
                self.by_code[g.system_code] = g.id
        for lg in self.ledgers.values():
            if lg.system_code:
                self.ledger_by_code[lg.system_code] = lg.id

    def depth(self, group_id: uuid.UUID) -> int:
        d, cur = 0, self.groups[group_id].parent_id
        while cur is not None:
            d, cur = d + 1, self.groups[cur].parent_id
        return d

    def primary(self, group_id: uuid.UUID) -> GroupNode:
        g = self.groups[group_id]
        while g.parent_id is not None:
            g = self.groups[g.parent_id]
        return g

    def ancestors(self, group_id: uuid.UUID) -> list[uuid.UUID]:
        out, cur = [], group_id
        while cur is not None:
            out.append(cur)
            cur = self.groups[cur].parent_id
        return out

    def subtree(self, *codes_or_ids: str | uuid.UUID) -> set[uuid.UUID]:
        roots = [self.by_code.get(c) if isinstance(c, str) else c for c in codes_or_ids]
        out: set[uuid.UUID] = set()
        stack = [r for r in roots if r is not None]
        while stack:
            gid = stack.pop()
            if gid in out:
                continue
            out.add(gid)
            stack.extend(self.children.get(gid, []))
        return out

    def ledgers_in(self, *codes_or_ids: str | uuid.UUID) -> list[LedgerNode]:
        gids = self.subtree(*codes_or_ids)
        return [lg for lg in self.ledgers.values() if lg.group_id in gids]

    def nature(self, ledger_id: uuid.UUID) -> str:
        return self.groups[self.ledgers[ledger_id].group_id].nature

    def in_group(self, ledger_id: uuid.UUID, code: str) -> bool:
        gid = self.by_code.get(code)
        return gid is not None and gid in self.ancestors(self.ledgers[ledger_id].group_id)


# ---------------------------------------------------------------- outstanding bills
@dataclass(frozen=True, slots=True)
class BillEntry:
    date: date
    voucher_number: str
    entry_type: str
    amount: Decimal
    allocations: list[dict[str, Any]]


@dataclass(slots=True)
class Bill:
    ref_name: str
    bill_date: date
    due_date: date | None
    amount: Decimal  # absolute original value
    pending: Decimal  # signed (DR +)


def outstanding_bills(
    *,
    natural_side: str,
    opening: Decimal,
    opening_date: date,
    credit_days: int | None,
    entries: list[BillEntry],
) -> list[Bill]:
    """Bill-wise outstanding: NEW_REF/ADVANCE create bills, AGAINST_REF settles by name, ON_ACCOUNT and
    unallocated settlements are knocked off FIFO against the oldest opposite bills; unallocated entries on the
    natural side (DR for debtors, CR for creditors) become bills named after the voucher number."""
    bills: OrderedDict[str, Bill] = OrderedDict()
    pool = ZERO
    last_date = opening_date

    def due(d: date, explicit: Any) -> date | None:
        if explicit:
            return explicit if isinstance(explicit, date) else date.fromisoformat(str(explicit))
        return d + timedelta(days=credit_days) if credit_days else None

    def add_bill(name: str, d: date, value: Decimal, due_date: date | None) -> None:
        if name in bills:
            bills[name].pending += value
            bills[name].amount += abs(value)
            return
        bills[name] = Bill(name, d, due_date, abs(value), value)

    if opening:
        add_bill("Opening Balance", opening_date, opening, None)
    for e in sorted(entries, key=lambda e: e.date):
        last_date = max(last_date, e.date)
        sign = Decimal(1) if e.entry_type == "DR" else Decimal(-1)
        allocated = ZERO
        for a in e.allocations or []:
            amt = Decimal(str(a["amount"]))
            allocated += amt
            value = sign * amt
            ref, kind = str(a.get("ref_name") or e.voucher_number), a.get("ref_type", "NEW_REF")
            if kind in ("NEW_REF", "ADVANCE"):
                add_bill(ref, e.date, value, due(e.date, a.get("due_date")))
            elif kind == "AGAINST_REF" and ref in bills:
                bills[ref].pending += value
            else:
                pool += value
        rest = e.amount - allocated
        if rest > 0:
            if e.entry_type == natural_side:
                name, n = e.voucher_number, 2
                while name in bills:
                    name, n = f"{e.voucher_number} ({n})", n + 1
                add_bill(name, e.date, sign * rest, due(e.date, None))
            else:
                pool += sign * rest
    # knock off the pool and any opposite-signed bills FIFO
    for b in bills.values():
        if pool == 0:
            break
        if b.pending == 0 or (b.pending > 0) == (pool > 0):
            continue
        used = min(abs(pool), abs(b.pending))
        if b.pending > 0:
            b.pending -= used
            pool += used
        else:
            b.pending += used
            pool -= used
    if pool != 0:
        add_bill("On Account", last_date, pool, None)
    return [b for b in bills.values() if b.pending != 0]


def bucket_edges(spec: str | None) -> list[int]:
    if not spec:
        return [30, 60, 90]
    edges = sorted({int(x) for x in spec.replace(" ", "").split(",") if x})
    if not edges or edges[0] <= 0:
        raise ValueError("buckets must be positive day counts like 30,60,90")
    return edges


def bucket_labels(edges: list[int]) -> list[str]:
    labels, lo = [], 0
    for e in edges:
        labels.append(f"{lo}-{e}")
        lo = e + 1
    labels.append(f">{edges[-1]}")
    return labels


def bucket_for(age_days: int, edges: list[int]) -> int:
    for i, e in enumerate(edges):
        if age_days <= e:
            return i
    return len(edges)
