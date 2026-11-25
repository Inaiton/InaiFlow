"""Financial reports, dashboard, exceptions and exports (plan §3.8: only REGULAR vouchers of accounting types).

* Trial balance: ledger balances (opening as at date_from, period DR/CR, closing), grouped (tree) or ledger mode.
* P&L (T-format): trading section (opening stock, purchase/direct groups, closing stock) -> gross profit,
  then indirect groups -> net profit. Stock comes from inventory valuation, not ledgers.
* Balance sheet (Schedule III style): cumulative profit since books beginning flows to Reserves & Surplus;
  "Difference in opening balances" (ledger openings + opening stock) is shown when non-zero, so the sheet
  always ties out when vouchers balance.
* Cash flow (indirect): net profit, depreciation add-back, inventory and working-capital changes (operating),
  fixed assets / investments (investing), capital / loans incl. bank OD (financing). Cash = cash-in-hand + bank.
"""

from __future__ import annotations

import csv
import io
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.export import Letterhead, Report, get_exporter
from app.core.context import TenantContext
from app.core.errors import ValidationFailedError
from app.core.fy import add_months, format_month, month_start
from app.core.money import ZERO, q2, to_str
from app.core.pagination import Page, PageParams
from app.core.security import csv_safe
from app.modules.accounts import common
from app.modules.accounts import repository as repo
from app.modules.accounts.inventory_service import stock_summary, total_stock_value
from app.modules.accounts.ledger_math import Chart, bucket_edges, bucket_for, bucket_labels, split
from app.modules.accounts.models import CostCentre, Ledger, StockItem, Voucher
from app.modules.accounts.schemas import (
    AccountsDashboardOut,
    AgeingOut,
    AgeingRow,
    AlertOut,
    BalanceSheetOut,
    BatchCostRow,
    CashFlowOut,
    CashFlowPoint,
    ExceptionOut,
    KpiOut,
    ProfitLossOut,
    RatioOut,
    StatementSection,
    TrialBalanceOut,
    TrialBalanceRow,
    VoucherSummary,
)
from app.modules.accounts.service import compute_bills
from app.modules.accounts.voucher_service import summaries
from app.modules.operations import interface as operations

CASH_GROUPS = ("CASH_IN_HAND", "BANK_ACCOUNTS")
MSME_DAYS = 45


def _check_range(date_from: date, date_to: date) -> None:
    if date_from > date_to:
        raise ValidationFailedError("date_from must be on or before date_to")


@dataclass
class Period:
    chart: Chart
    opening: dict[uuid.UUID, Decimal]  # signed balance at the start of date_from
    dr: dict[uuid.UUID, Decimal]
    cr: dict[uuid.UUID, Decimal]

    def move(self, lid: uuid.UUID) -> Decimal:
        return self.dr.get(lid, ZERO) - self.cr.get(lid, ZERO)

    def closing(self, lid: uuid.UUID) -> Decimal:
        return self.opening[lid] + self.move(lid)


async def period(db: AsyncSession, ctx: TenantContext, date_from: date, date_to: date) -> Period:
    chart = await repo.load_chart(db, ctx.org_id)
    before = await repo.ledger_totals(db, ctx.org_id, date_to=date_from - timedelta(days=1))
    within = await repo.ledger_totals(db, ctx.org_id, date_from=date_from, date_to=date_to)
    opening = {lid: lg.opening + before.get(lid, (ZERO, ZERO))[0] - before.get(lid, (ZERO, ZERO))[1]
               for lid, lg in chart.ledgers.items()}  # fmt: skip
    return Period(chart, opening, {k: v[0] for k, v in within.items()}, {k: v[1] for k, v in within.items()})


# ================================================================= trial balance
async def trial_balance(db: AsyncSession, ctx: TenantContext, date_from: date, date_to: date, mode: str | None
                        ) -> TrialBalanceOut:  # fmt: skip
    _check_range(date_from, date_to)
    mode = (mode or "grouped").lower()
    if mode not in ("grouped", "ledger"):
        raise ValidationFailedError("mode must be grouped or ledger")
    p = await period(db, ctx, date_from, date_to)
    chart = p.chart

    def vals(lids: list[uuid.UUID]) -> tuple[Decimal, Decimal, Decimal, Decimal]:
        o = sum((p.opening[i] for i in lids), ZERO)
        return o, sum((p.dr.get(i, ZERO) for i in lids), ZERO), sum((p.cr.get(i, ZERO) for i in lids), ZERO), \
            sum((p.closing(i) for i in lids), ZERO)  # fmt: skip

    def row(kind: str, oid: uuid.UUID, name: str, level: int, parent: uuid.UUID | None, lids: list) -> TrialBalanceRow:
        o, d, c, cl = vals(lids)
        oa, ot = split(o)
        ca, ct = split(cl)
        return TrialBalanceRow(kind=kind, id=oid, name=name, level=level, parent_id=parent,
                               opening_dr=oa if ot == "DR" else ZERO, opening_cr=oa if ot == "CR" else ZERO,
                               debit=d, credit=c, closing_dr=ca if ct == "DR" else ZERO,
                               closing_cr=ca if ct == "CR" else ZERO)  # fmt: skip

    def active(lid: uuid.UUID) -> bool:
        return p.opening[lid] != 0 or p.dr.get(lid, ZERO) != 0 or p.cr.get(lid, ZERO) != 0

    rows: list[TrialBalanceRow] = []
    if mode == "ledger":
        for lg in sorted(chart.ledgers.values(), key=lambda x: x.name):
            if active(lg.id):
                rows.append(row("LEDGER", lg.id, lg.name, 0, lg.group_id, [lg.id]))
    else:

        def walk(gid: uuid.UUID, level: int) -> None:
            lids = [lg.id for lg in chart.ledgers_in(gid) if active(lg.id)]
            if not lids:
                return
            g = chart.groups[gid]
            rows.append(row("GROUP", gid, g.name, level, g.parent_id, lids))
            for child in chart.children.get(gid, []):
                walk(child, level + 1)
            for lg in sorted(
                (x for x in chart.ledgers.values() if x.group_id == gid and active(x.id)), key=lambda x: x.name
            ):
                rows.append(row("LEDGER", lg.id, lg.name, level + 1, gid, [lg.id]))

        for gid in chart.children.get(None, []):
            walk(gid, 0)
    leaf = [r for r in rows if r.kind == "LEDGER"]
    tdr = sum((r.closing_dr for r in leaf), ZERO)
    tcr = sum((r.closing_cr for r in leaf), ZERO)
    return TrialBalanceOut(date_from=date_from, date_to=date_to, rows=rows, total_debit=tdr, total_credit=tcr,
                           difference=tdr - tcr)  # fmt: skip


# ================================================================= statements
def _section(chart: Chart, gid: uuid.UUID, values: dict[uuid.UUID, Decimal], sign: int,
             exclude: set[uuid.UUID] = frozenset()) -> StatementSection | None:  # fmt: skip
    if gid in exclude:
        return None
    children = [s for c in chart.children.get(gid, []) if (s := _section(chart, c, values, sign, exclude))]
    for lg in sorted((x for x in chart.ledgers.values() if x.group_id == gid), key=lambda x: x.name):
        v = values.get(lg.id, ZERO) * sign
        if v != 0:
            children.append(StatementSection(label=lg.name, amount=v, group_id=None))
    if not children:
        return None
    return StatementSection(label=chart.groups[gid].name, amount=sum((c.amount for c in children), ZERO),
                            group_id=gid, children=children)  # fmt: skip


def _total(sections: list[StatementSection]) -> Decimal:
    return sum((s.amount for s in sections), ZERO)


def _pl_sections(chart: Chart, values: dict[uuid.UUID, Decimal], opening_stock: Decimal, closing_stock: Decimal
                 ) -> dict[str, Any]:  # fmt: skip
    td: list[StatementSection] = []
    tc: list[StatementSection] = []
    pd: list[StatementSection] = []
    pc: list[StatementSection] = []
    if opening_stock:
        td.append(StatementSection(label="Opening Stock", amount=opening_stock))
    for gid in chart.children.get(None, []):
        g = chart.groups[gid]
        if g.nature not in ("INCOME", "EXPENSES"):
            continue
        expense = g.nature == "EXPENSES"
        s = _section(chart, gid, values, 1 if expense else -1)
        if s:
            (td if expense else tc).append(s) if g.affects_gross_profit else (pd if expense else pc).append(s)
    if closing_stock:
        tc.append(StatementSection(label="Closing Stock", amount=closing_stock))
    gp = _total(tc) - _total(td)
    return {"trading_debit": td, "trading_credit": tc, "gross_profit": gp, "pnl_debit": pd, "pnl_credit": pc,
            "net_profit": gp + _total(pc) - _total(pd)}  # fmt: skip


async def _pl_values(db: AsyncSession, ctx: TenantContext, date_from: date, date_to: date) -> tuple[Period, dict]:
    p = await period(db, ctx, date_from, date_to)
    org = await common.org_brief(db, ctx)
    include_opening = date_from <= org.books_beginning_from
    values = {lid: p.move(lid) + (lg.opening if include_opening else ZERO) for lid, lg in p.chart.ledgers.items()}
    return p, values


async def profit_loss(db: AsyncSession, ctx: TenantContext, date_from: date, date_to: date) -> ProfitLossOut:
    _check_range(date_from, date_to)
    p, values = await _pl_values(db, ctx, date_from, date_to)
    os_ = await total_stock_value(db, ctx.org_id, date_from - timedelta(days=1))
    cs = await total_stock_value(db, ctx.org_id, date_to)
    return ProfitLossOut(date_from=date_from, date_to=date_to, closing_stock=cs, opening_stock=os_,
                         **_pl_sections(p.chart, values, os_, cs))  # fmt: skip


async def balance_sheet(db: AsyncSession, ctx: TenantContext, as_of: date) -> BalanceSheetOut:
    org = await common.org_brief(db, ctx)
    chart = await repo.load_chart(db, ctx.org_id)
    bal = await repo.balances(db, chart, ctx.org_id, as_of)
    os0 = await total_stock_value(db, ctx.org_id, org.books_beginning_from - timedelta(days=1))
    cs = await total_stock_value(db, ctx.org_id, as_of)
    profit = _pl_sections(chart, bal, os0, cs)["net_profit"]
    sec = {code: chart.by_code.get(code) for code in ("CAPITAL_ACCOUNT", "LOANS_LIABILITY", "BANK_OD",
           "CURRENT_LIABILITIES", "BRANCH_DIVISIONS", "SUSPENSE", "FIXED_ASSETS", "INVESTMENTS", "MISC_EXPENSES_ASSET",
           "CURRENT_ASSETS")}  # fmt: skip

    def s(code: str, sign: int, exclude: set | None = None) -> list[StatementSection]:
        gid = sec.get(code)
        out = _section(chart, gid, bal, sign, exclude or set()) if gid else None
        return [out] if out else []

    funds = s("CAPITAL_ACCOUNT", -1)
    pl_row = StatementSection(label="Profit & Loss A/c (Surplus)", amount=profit)
    funds_children = [*funds, pl_row] if profit else funds
    bank_od = chart.subtree(sec["BANK_OD"]) if sec.get("BANK_OD") else set()
    liabilities = [
        StatementSection(label="Shareholders' Funds", amount=_total(funds_children), children=funds_children),
        StatementSection(label="Non-Current Liabilities", amount=_total(s("LOANS_LIABILITY", -1, bank_od)),
                         children=s("LOANS_LIABILITY", -1, bank_od)),
    ]  # fmt: skip
    cur_l = [*s("CURRENT_LIABILITIES", -1), *s("BANK_OD", -1), *s("BRANCH_DIVISIONS", -1), *s("SUSPENSE", -1)]
    liabilities.append(StatementSection(label="Current Liabilities", amount=_total(cur_l), children=cur_l))
    non_cur_a = [*s("FIXED_ASSETS", 1), *s("INVESTMENTS", 1), *s("MISC_EXPENSES_ASSET", 1)]
    cur_a = s("CURRENT_ASSETS", 1)
    if cs:
        cur_a.append(StatementSection(label="Closing Stock (inventory)", amount=cs))
    assets = [StatementSection(label="Non-Current Assets", amount=_total(non_cur_a), children=non_cur_a),
              StatementSection(label="Current Assets", amount=_total(cur_a), children=cur_a)]  # fmt: skip
    diff = sum((lg.opening for lg in chart.ledgers.values()), ZERO) + os0
    if diff > 0:
        liabilities.append(StatementSection(label="Difference in Opening Balances", amount=diff))
    elif diff < 0:
        assets.append(StatementSection(label="Difference in Opening Balances", amount=-diff))
    tl, ta = _total(liabilities), _total(assets)
    return BalanceSheetOut(as_of=as_of, equity_and_liabilities=liabilities, assets=assets, total_liabilities=tl,
                           total_assets=ta, difference=ta - tl)  # fmt: skip


async def cash_flow(db: AsyncSession, ctx: TenantContext, date_from: date, date_to: date) -> CashFlowOut:
    _check_range(date_from, date_to)
    p = await period(db, ctx, date_from, date_to)
    chart = p.chart
    cash_ids = {lg.id for lg in chart.ledgers_in(*CASH_GROUPS)}
    os_ = await total_stock_value(db, ctx.org_id, date_from - timedelta(days=1))
    cs = await total_stock_value(db, ctx.org_id, date_to)
    pl_ids = {lid for lid in chart.ledgers if chart.nature(lid) in ("INCOME", "EXPENSES")}
    np = -sum((p.move(lid) for lid in pl_ids), ZERO) + cs - os_
    dep = sum((p.move(lg.id) for lg in chart.ledgers_in("INDIRECT_EXPENSES") if "depreci" in lg.name.lower()), ZERO)

    def change(*codes: str, exclude: set[uuid.UUID] = frozenset()) -> list[StatementSection]:
        out = []
        for code in codes:
            gid = chart.by_code.get(code)
            if gid is None:
                continue
            moves = {lid: p.move(lid) for lid in chart.ledgers if lid not in cash_ids}
            s = _section(
                chart, gid, moves, -1, set(exclude) | {chart.by_code[c] for c in CASH_GROUPS if c in chart.by_code}
            )
            if s:
                out.append(s)
        return out

    operating = [StatementSection(label="Net Profit", amount=np)]
    if dep:
        operating.append(StatementSection(label="Add: Depreciation", amount=dep))
    if cs - os_:
        operating.append(StatementSection(label="(Increase) / Decrease in Inventory", amount=-(cs - os_)))
    operating += change("CURRENT_ASSETS", "CURRENT_LIABILITIES", "MISC_EXPENSES_ASSET", "BRANCH_DIVISIONS", "SUSPENSE")
    investing = change("FIXED_ASSETS", "INVESTMENTS")
    if dep:
        investing.append(StatementSection(label="Less: Depreciation charged to assets", amount=-dep))
    financing = change("CAPITAL_ACCOUNT", "LOANS_LIABILITY")
    opening_cash = sum((p.opening[i] for i in cash_ids), ZERO)
    closing_cash = sum((p.closing(i) for i in cash_ids), ZERO)
    return CashFlowOut(date_from=date_from, date_to=date_to, operating=operating, investing=investing,
                       financing=financing, net_change=closing_cash - opening_cash, opening_cash=opening_cash,
                       closing_cash=closing_cash)  # fmt: skip


async def ratios(db: AsyncSession, ctx: TenantContext, date_from: date, date_to: date) -> list[RatioOut]:
    _check_range(date_from, date_to)
    p, values = await _pl_values(db, ctx, date_from, date_to)
    chart = p.chart
    os_ = await total_stock_value(db, ctx.org_id, date_from - timedelta(days=1))
    cs = await total_stock_value(db, ctx.org_id, date_to)
    pl = _pl_sections(chart, values, os_, cs)

    def bal(*codes: str, sign: int = 1) -> Decimal:
        return sum((p.closing(lg.id) for lg in chart.ledgers_in(*codes)), ZERO) * sign

    def flow(*codes: str, sign: int = 1) -> Decimal:
        return sum((values[lg.id] for lg in chart.ledgers_in(*codes)), ZERO) * sign

    ca = bal("CURRENT_ASSETS") + cs
    cl = bal("CURRENT_LIABILITIES", sign=-1) + bal("BANK_OD", sign=-1)
    equity = bal("CAPITAL_ACCOUNT", sign=-1) + pl["net_profit"]
    debt = bal("LOANS_LIABILITY", sign=-1)
    sales = flow("SALES_ACCOUNTS", sign=-1)
    purchases = flow("PURCHASE_ACCOUNTS")
    days = Decimal((date_to - date_from).days + 1)
    cogs = os_ + purchases + flow("DIRECT_EXPENSES") - cs
    avg_inv = (os_ + cs) / 2

    def div(a: Decimal, b: Decimal, mul: Decimal = Decimal(1)) -> Decimal | None:
        return q2(a * mul / b) if b else None

    return [
        RatioOut(key="current_ratio", label="Current Ratio", value=div(ca, cl), formula="Current Assets / Current Liabilities"),
        RatioOut(key="quick_ratio", label="Quick Ratio", value=div(ca - cs, cl),
                 formula="(Current Assets - Closing Stock) / Current Liabilities"),
        RatioOut(key="debt_equity", label="Debt-Equity Ratio", value=div(debt, equity),
                 formula="Loans (Liability) / (Capital + Reserves + Profit)"),
        RatioOut(key="gross_margin_pct", label="Gross Profit %", value=div(pl["gross_profit"], sales, Decimal(100)),
                 formula="Gross Profit / Sales x 100"),
        RatioOut(key="net_margin_pct", label="Net Profit %", value=div(pl["net_profit"], sales, Decimal(100)),
                 formula="Net Profit / Sales x 100"),
        RatioOut(key="debtor_days", label="Receivable Turnover in Days", value=div(bal("SUNDRY_DEBTORS"), sales, days),
                 formula="Sundry Debtors / Sales x Days"),
        RatioOut(key="creditor_days", label="Payable Turnover in Days",
                 value=div(bal("SUNDRY_CREDITORS", sign=-1), purchases, days), formula="Sundry Creditors / Purchases x Days"),
        RatioOut(key="inventory_turnover", label="Inventory Turnover", value=div(cogs, avg_inv),
                 formula="Cost of Goods Sold / Average Inventory"),
    ]  # fmt: skip


# ================================================================= ageing / day book / batch costing
async def ageing(db: AsyncSession, ctx: TenantContext, kind: str, as_of: date, buckets: str | None) -> AgeingOut:
    k = kind.upper().rstrip("S")
    if k not in ("RECEIVABLE", "PAYABLE"):
        raise ValidationFailedError("kind must be RECEIVABLE or PAYABLE")
    try:
        edges = bucket_edges(buckets)
    except ValueError as exc:
        raise ValidationFailedError(str(exc)) from exc
    labels = bucket_labels(edges)
    chart = await repo.load_chart(db, ctx.org_id)
    parties = chart.ledgers_in("SUNDRY_DEBTORS" if k == "RECEIVABLE" else "SUNDRY_CREDITORS")
    bills = await compute_bills(db, ctx, [lg.id for lg in parties], as_of, chart)
    sign = 1 if k == "RECEIVABLE" else -1
    rows, totals = [], dict.fromkeys([*labels, "total"], ZERO)
    for lg in sorted(parties, key=lambda x: x.name):
        b = dict.fromkeys(labels, ZERO)
        msme = False
        for bill in bills[lg.id]:
            age = max(0, (as_of - bill.bill_date).days)
            amount = bill.pending * sign
            b[labels[bucket_for(age, edges)]] += amount
            if k == "PAYABLE" and lg.party_details.get("msme_type") and amount > 0 and age > MSME_DAYS:
                msme = True
        total = sum(b.values(), ZERO)
        if total == 0 and not any(b.values()):
            continue
        rows.append(AgeingRow(ledger_id=lg.id, party_name=lg.name, total=total, buckets=b, msme_overdue=msme))
        for lab in labels:
            totals[lab] += b[lab]
        totals["total"] += total
    return AgeingOut(kind=k, as_of=as_of, bucket_labels=labels, rows=rows, totals=totals)


async def day_book(db: AsyncSession, ctx: TenantContext, date_from: date, date_to: date, page: PageParams
                   ) -> Page[VoucherSummary]:  # fmt: skip
    _check_range(date_from, date_to)
    stmt = (select(Voucher).where(Voucher.org_id == ctx.org_id, Voucher.voucher_date.between(date_from, date_to))
            .order_by(Voucher.voucher_date, Voucher.created_at))  # fmt: skip
    rows, total = await repo.page_scalars(db, stmt, page)
    return Page[VoucherSummary](items=await summaries(db, ctx, rows), total=total, limit=page.limit, offset=page.offset)


async def batch_costing(db: AsyncSession, ctx: TenantContext, date_from: date, date_to: date) -> list[BatchCostRow]:
    _check_range(date_from, date_to)
    chart = await repo.load_chart(db, ctx.org_id)
    ccs = [c for c in await repo.list_all(db, CostCentre, ctx.org_id, CostCentre.name) if c.linked_period_run_id]
    cc_run = {c.id: c.linked_period_run_id for c in ccs}
    stmt = repo.entry_rows_stmt(ctx.org_id).where(Voucher.voucher_date.between(date_from, date_to))
    rows = list((await db.execute(stmt)).all())
    dr: dict[uuid.UUID, Decimal] = defaultdict(lambda: ZERO)
    cr: dict[uuid.UUID, Decimal] = defaultdict(lambda: ZERO)
    for e, v, _vt, _bt in rows:
        run = cc_run.get(e.cost_centre_id) if e.cost_centre_id else None
        if run is not None:
            (dr if e.entry_type == "DR" else cr)[run] += e.amount
        elif v.linked_period_run_id:
            run = v.linked_period_run_id
            nature = chart.nature(e.ledger_id)
            if e.entry_type == "DR" and nature == "EXPENSES":
                dr[run] += e.amount
            elif e.entry_type == "CR" and nature == "INCOME":
                cr[run] += e.amount
            else:
                continue
        else:
            continue
    listed = {r.id: r for r in await operations.list_runs_for_costing(db, ctx, date_from, date_to)}
    extra = [rid for rid in set(dr) | set(cr) if rid not in listed]
    runs = {**listed, **{r.id: r for r in await operations.get_runs_by_ids(db, ctx, extra)}} if extra else listed
    items = await repo.get_many(db, StockItem, ctx.org_id, [r.stock_item_id for r in runs.values() if r.stock_item_id])
    out = []
    for r in sorted(runs.values(), key=lambda r: (r.period_month, r.run_title)):
        net = dr[r.id] - cr[r.id]
        item = items.get(r.stock_item_id)
        out.append(BatchCostRow(period_run_id=r.id, run_title=r.run_title, period_month=r.period_month,
                                stock_item_name=item.name if item else None, accepted_qty=r.accepted_qty,
                                rejected_qty=r.rejected_qty, total_debit=dr[r.id], total_credit=cr[r.id], net_cost=net,
                                unit_cost=q2(net / r.accepted_qty) if r.accepted_qty else ZERO, status=r.status))  # fmt: skip
    return out


# ================================================================= dashboard / exceptions
async def _balance_by_groups(
    db: AsyncSession, ctx: TenantContext, chart: Chart, as_of: date | None, *codes: str
) -> Decimal:
    bal = await repo.balances(db, chart, ctx.org_id, as_of)
    return sum((bal[lg.id] for lg in chart.ledgers_in(*codes)), ZERO)


async def dashboard(db: AsyncSession, ctx: TenantContext, today: date | None = None) -> AccountsDashboardOut:
    today = today or date.today()
    chart = await repo.load_chart(db, ctx.org_id)
    bal = await repo.balances(db, chart, ctx.org_id, today)

    def g(*codes: str, sign: int = 1) -> Decimal:
        return sum((bal[lg.id] for lg in chart.ledgers_in(*codes)), ZERO) * sign

    mstart = month_start(today)
    prev_start = add_months(mstart, -1)
    prev_end = min(add_months(today, -1), mstart - timedelta(days=1))
    cur = await repo.ledger_totals(db, ctx.org_id, date_from=mstart, date_to=today)
    prev = await repo.ledger_totals(db, ctx.org_id, date_from=prev_start, date_to=prev_end)

    def flow(totals: dict, code: str, sign: int) -> Decimal:
        return sum(((totals.get(lg.id, (ZERO, ZERO))[0] - totals.get(lg.id, (ZERO, ZERO))[1]) * sign
                    for lg in chart.ledgers_in(code)), ZERO)  # fmt: skip

    def pct(a: Decimal, b: Decimal) -> Decimal | None:
        return q2((a - b) * 100 / b) if b else None

    sales, sales_prev = flow(cur, "SALES_ACCOUNTS", -1), flow(prev, "SALES_ACCOUNTS", -1)
    purch, purch_prev = flow(cur, "PURCHASE_ACCOUNTS", 1), flow(prev, "PURCHASE_ACCOUNTS", 1)
    out_codes, in_codes = ("CGST_OUT", "SGST_OUT", "IGST_OUT", "RCM_PAYABLE"), ("CGST_IN", "SGST_IN", "IGST_IN")
    gst = -sum((bal[chart.ledger_by_code[c]] for c in out_codes if c in chart.ledger_by_code), ZERO) - \
        sum((bal[chart.ledger_by_code[c]] for c in in_codes if c in chart.ledger_by_code), ZERO)  # fmt: skip
    kpis = [
        KpiOut(key="cash_bank", label="Cash & Bank", value=g(*CASH_GROUPS), change_pct=None),
        KpiOut(key="receivables", label="Receivables", value=g("SUNDRY_DEBTORS"), change_pct=None),
        KpiOut(key="payables", label="Payables", value=g("SUNDRY_CREDITORS", sign=-1), change_pct=None),
        KpiOut(key="sales_mtd", label="Sales (MTD)", value=sales, change_pct=pct(sales, sales_prev)),
        KpiOut(key="purchases_mtd", label="Purchases (MTD)", value=purch, change_pct=pct(purch, purch_prev)),
        KpiOut(key="gst_payable", label="GST Payable (net)", value=gst, change_pct=None),
    ]
    cash_ids = [lg.id for lg in chart.ledgers_in(*CASH_GROUPS)]
    six = add_months(mstart, -5)
    monthly = await repo.monthly_ledger_totals(db, ctx.org_id, cash_ids, six, today, ("CONTRA",)) if cash_ids else []
    agg: dict[str, list[Decimal]] = {format_month(add_months(six, i)): [ZERO, ZERO] for i in range(6)}
    for m, side, amount in monthly:
        key = format_month(m.date() if hasattr(m, "date") else m)
        if key in agg:
            agg[key][0 if side == "DR" else 1] += Decimal(amount)
    cash_flow_pts = [CashFlowPoint(month=k, inflow=v[0], outflow=v[1]) for k, v in agg.items()]
    alerts = [AlertOut(severity=e.severity, kind=e.kind, message=e.message, link=e.link)
              for e in await exceptions(db, ctx, today, chart=chart) if e.kind in
              ("MSME_OVERDUE", "NEGATIVE_STOCK", "LOW_STOCK", "UNRECONCILED_BANK")]  # fmt: skip
    recent = (await db.execute(select(Voucher).where(Voucher.org_id == ctx.org_id)
                               .order_by(Voucher.created_at.desc()).limit(10))).scalars().all()  # fmt: skip
    return AccountsDashboardOut(kpis=kpis, cash_flow=cash_flow_pts, alerts=alerts,
                                recent_vouchers=await summaries(db, ctx, list(recent)))  # fmt: skip


async def exceptions(db: AsyncSession, ctx: TenantContext, today: date | None = None, *, chart: Chart | None = None
                     ) -> list[ExceptionOut]:  # fmt: skip
    today = today or date.today()
    chart = chart or await repo.load_chart(db, ctx.org_id)
    org = await common.org_brief(db, ctx)
    bal = await repo.balances(db, chart, ctx.org_id, None)
    out: list[ExceptionOut] = []
    for row in await stock_summary(db, ctx, as_of=None, godown_id=None, stock_group_id=None):
        link = f"/accounts/masters/inventory/{row.stock_item_id}"
        if row.quantity < 0:
            out.append(ExceptionOut(kind="NEGATIVE_STOCK", severity="ERROR", entity_type="stock_item",
                                    entity_id=row.stock_item_id, link=link,
                                    message=f"{row.name} has negative stock ({to_str(row.quantity)} {row.uom})"))  # fmt: skip
        elif row.below_reorder:
            out.append(ExceptionOut(kind="LOW_STOCK", severity="WARNING", entity_type="stock_item",
                                    entity_id=row.stock_item_id, link=link,
                                    message=f"{row.name} is below its reorder level ({to_str(row.quantity)} {row.uom})"))  # fmt: skip
    for lg in chart.ledgers_in("CASH_IN_HAND"):
        if bal[lg.id] < 0:
            out.append(ExceptionOut(kind="NEGATIVE_CASH", severity="ERROR", entity_type="ledger", entity_id=lg.id,
                                    link=f"/accounts/masters/ledgers/{lg.id}",
                                    message=f"{lg.name} has a credit balance of {to_str(-bal[lg.id])}"))  # fmt: skip
    debtors = {lg.id for lg in chart.ledgers_in("SUNDRY_DEBTORS")}
    if debtors:
        limits = await repo.get_many(db, Ledger, ctx.org_id, list(debtors))
        for lid, lg in limits.items():
            if lg.credit_limit and bal[lid] > lg.credit_limit:
                out.append(ExceptionOut(kind="CREDIT_LIMIT_EXCEEDED", severity="WARNING", entity_type="ledger",
                                        entity_id=lid, link=f"/accounts/masters/ledgers/{lid}",
                                        message=f"{lg.name} exceeds its credit limit ({to_str(bal[lid])} > {to_str(lg.credit_limit)})"))  # fmt: skip
    for r in (await ageing(db, ctx, "PAYABLE", today, None)).rows:
        if r.msme_overdue:
            out.append(ExceptionOut(kind="MSME_OVERDUE", severity="ERROR", entity_type="ledger", entity_id=r.ledger_id,
                                    link=f"/accounts/masters/ledgers/{r.ledger_id}",
                                    message=f"MSME supplier {r.party_name} has bills unpaid beyond {MSME_DAYS} days"))  # fmt: skip
    banks = chart.ledgers_in("BANK_ACCOUNTS", "BANK_OD")
    if banks:
        rows = await repo.ledger_entries(db, ctx.org_id, [b.id for b in banks], None, today - timedelta(days=30))
        stale: dict[uuid.UUID, int] = defaultdict(int)
        for e, *_ in rows:
            if e.bank_reconciliation_date is None:
                stale[e.ledger_id] += 1
        for lid, n in stale.items():
            out.append(ExceptionOut(kind="UNRECONCILED_BANK", severity="WARNING", entity_type="ledger", entity_id=lid,
                                    link=f"/accounts/banking/reconciliation?ledger_id={lid}",
                                    message=f"{chart.ledgers[lid].name}: {n} entries older than 30 days are unreconciled"))  # fmt: skip
    due = (await db.execute(select(Voucher.id, Voucher.voucher_number).where(
        Voucher.org_id == ctx.org_id, Voucher.status == "POST_DATED", Voucher.voucher_date <= today))).all()  # fmt: skip
    for vid, number in due:
        out.append(ExceptionOut(kind="POST_DATED_DUE", severity="INFO", entity_type="voucher", entity_id=vid,
                                link=f"/accounts/vouchers/{vid}",
                                message=f"Post-dated voucher {number} has reached its date; convert it to regular"))  # fmt: skip
    os0 = await total_stock_value(db, ctx.org_id, org.books_beginning_from - timedelta(days=1))
    diff = sum((lg.opening for lg in chart.ledgers.values()), ZERO) + os0
    if diff:
        amount, kind = split(diff)
        out.append(ExceptionOut(kind="OPENING_DIFFERENCE", severity="WARNING", entity_type="organization",
                                entity_id=ctx.org_id, link="/accounts/reports/trial-balance",
                                message=f"Opening balances differ by {to_str(amount)} {kind}"))  # fmt: skip
    return out


# ================================================================= exports
def _flatten(sections: list[StatementSection], side: str, depth: int = 0) -> list[list[str]]:
    rows = []
    for s in sections:
        rows.append([side, "  " * depth + s.label, to_str(s.amount)])
        rows += _flatten(s.children, side, depth + 1)
    return rows


async def export_table(db: AsyncSession, ctx: TenantContext, report: str, q: dict[str, Any]
                       ) -> tuple[str, list[str], list[list[str]]]:  # fmt: skip
    def need(*keys: str) -> None:
        missing = [k for k in keys if not q.get(k)]
        if missing:
            raise ValidationFailedError(f"{report} export needs {', '.join(missing)}")

    if report == "trial-balance":
        need("date_from", "date_to")
        tb = await trial_balance(db, ctx, q["date_from"], q["date_to"], q.get("mode"))
        return ("Trial Balance", ["Particulars", "Opening Dr", "Opening Cr", "Debit", "Credit", "Closing Dr", "Closing Cr"],
                [["  " * r.level + r.name, *(to_str(x) for x in (r.opening_dr, r.opening_cr, r.debit, r.credit,
                                                                r.closing_dr, r.closing_cr))] for r in tb.rows]
                + [["Total", "", "", "", "", to_str(tb.total_debit), to_str(tb.total_credit)]])  # fmt: skip
    if report == "profit-loss":
        need("date_from", "date_to")
        pl = await profit_loss(db, ctx, q["date_from"], q["date_to"])
        rows = (_flatten(pl.trading_debit, "Dr") + _flatten(pl.trading_credit, "Cr")
                + [["", "Gross Profit", to_str(pl.gross_profit)]] + _flatten(pl.pnl_debit, "Dr")
                + _flatten(pl.pnl_credit, "Cr") + [["", "Net Profit", to_str(pl.net_profit)]])  # fmt: skip
        return "Profit & Loss A/c", ["Side", "Particulars", "Amount"], rows
    if report == "balance-sheet":
        need("as_of")
        bs = await balance_sheet(db, ctx, q["as_of"])
        rows = _flatten(bs.equity_and_liabilities, "Liabilities") + _flatten(bs.assets, "Assets")
        rows += [["", "Total Liabilities", to_str(bs.total_liabilities)], ["", "Total Assets", to_str(bs.total_assets)]]
        return "Balance Sheet", ["Side", "Particulars", "Amount"], rows
    if report == "cash-flow":
        need("date_from", "date_to")
        cf = await cash_flow(db, ctx, q["date_from"], q["date_to"])
        rows = (
            _flatten(cf.operating, "Operating")
            + _flatten(cf.investing, "Investing")
            + _flatten(cf.financing, "Financing")
        )
        rows += [["", "Net change in cash", to_str(cf.net_change)]]
        return "Cash Flow Statement", ["Activity", "Particulars", "Amount"], rows
    if report == "ratios":
        need("date_from", "date_to")
        return ("Ratio Analysis", ["Ratio", "Value", "Formula"],
                [[r.label, to_str(r.value) or "", r.formula] for r in await ratios(db, ctx, q["date_from"], q["date_to"])])  # fmt: skip
    if report == "ageing":
        need("as_of", "kind")
        a = await ageing(db, ctx, q["kind"], q["as_of"], q.get("buckets"))
        return (f"{a.kind.title()} Ageing", ["Party", *a.bucket_labels, "Total"],
                [[r.party_name, *(to_str(r.buckets[b]) for b in a.bucket_labels), to_str(r.total)] for r in a.rows])  # fmt: skip
    if report == "day-book":
        need("date_from", "date_to")
        page = await day_book(db, ctx, q["date_from"], q["date_to"], PageParams(200, 0))
        items, offset = list(page.items), 200
        while offset < page.total:
            items += (await day_book(db, ctx, q["date_from"], q["date_to"], PageParams(200, offset))).items
            offset += 200
        return ("Day Book", ["Date", "Type", "Number", "Party", "Amount", "Status"],
                [[v.voucher_date.isoformat(), v.voucher_type_name, v.voucher_number, v.party_name or "",
                  to_str(v.total_amount), v.status] for v in items])  # fmt: skip
    if report == "batch-costing":
        need("date_from", "date_to")
        return ("Batch Costing", ["Run", "Month", "Accepted", "Rejected", "Debit", "Credit", "Net", "Unit Cost"],
                [[r.run_title, format_month(r.period_month), to_str(r.accepted_qty), to_str(r.rejected_qty),
                  to_str(r.total_debit), to_str(r.total_credit), to_str(r.net_cost), to_str(r.unit_cost)]
                 for r in await batch_costing(db, ctx, q["date_from"], q["date_to"])])  # fmt: skip
    if report == "stock-summary":
        rows = await stock_summary(db, ctx, as_of=q.get("as_of"), godown_id=None, stock_group_id=None)
        return ("Stock Summary", ["Item", "Group", "Qty", "UoM", "Rate", "Value"],
                [[r.name, r.stock_group_name or "", to_str(r.quantity), r.uom, to_str(r.rate), to_str(r.value)] for r in rows])  # fmt: skip
    raise ValidationFailedError(f"Unknown report {report}", details={"allowed": EXPORTABLE})


EXPORTABLE = ["trial-balance", "profit-loss", "balance-sheet", "cash-flow", "ratios", "ageing", "day-book",
              "batch-costing", "stock-summary"]  # fmt: skip


async def export_report(db: AsyncSession, ctx: TenantContext, report: str, fmt: str, q: dict[str, Any]
                        ) -> tuple[bytes, str, str]:  # fmt: skip
    fmt = fmt.lower()
    if fmt not in ("csv", "pdf"):
        raise ValidationFailedError("format must be csv or pdf")
    title, columns, rows = await export_table(db, ctx, report, q)
    if fmt == "csv":
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(columns)
        w.writerows([[csv_safe(c) for c in row] for row in rows])
        return buf.getvalue().encode("utf-8-sig"), "text/csv", f"{report}.csv"
    org = await common.org_brief(db, ctx)
    span = " to ".join(str(q[k]) for k in ("date_from", "date_to") if q.get(k)) or (
        f"as of {q['as_of']}" if q.get("as_of") else ""
    )
    rep = Report(title=title, letterhead=Letterhead(name=org.legal_name, lines=org.address_lines),
                 blocks=[{"type": "heading", "data": {"text": f"{title} {span}".strip(), "level": 1}},
                         {"type": "table", "data": {"columns": columns, "rows": rows}}],
                 landscape=len(columns) > 5)  # fmt: skip
    return get_exporter().render(rep, "pdf"), "application/pdf", f"{report}.pdf"
