"""Run money flow (linked vouchers + run postings + payroll allocations), postings, voucher links,
manufacturing journal on completion."""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import write_audit
from app.core.context import TenantContext
from app.core.errors import NotFoundError, ValidationFailedError
from app.core.money import q4
from app.modules.accounts import interface as accounts
from app.modules.operations.common import ZERO, assert_run_access, dz, get_run, get_steps, today
from app.modules.operations.models import PeriodRun, PeriodRunCostLine, PeriodRunVoucherLink
from app.modules.operations.schemas import (
    LinkVoucherIn,
    MoneyFlowLine,
    MoneyFlowOut,
    RunPostingIn,
    RunPostingOut,
)

CREDIT_BASES = frozenset({"SALES", "RECEIPT"})
EXCLUDED_BASES = frozenset({"STOCK_JOURNAL", "MFG_JOURNAL", "PAYROLL", "MEMORANDUM", "PURCHASE_ORDER",
                            "SALES_ORDER", "PHYSICAL_STOCK"})  # fmt: skip


async def money_flow(db: AsyncSession, ctx: TenantContext, run: PeriodRun) -> MoneyFlowOut:
    lines = list((await db.execute(select(PeriodRunCostLine).where(PeriodRunCostLine.period_run_id == run.id)
                                   .order_by(PeriodRunCostLine.line_date, PeriodRunCostLine.created_at))).scalars())  # fmt: skip
    links = dict((await db.execute(select(PeriodRunVoucherLink.voucher_id, PeriodRunVoucherLink.step_id)
                                   .where(PeriodRunVoucherLink.period_run_id == run.id))).all())  # fmt: skip
    posting_ids = {ln.voucher_id for ln in lines if ln.voucher_id}
    debits: list[MoneyFlowLine] = []
    credits: list[MoneyFlowLine] = []
    for v in await accounts.list_vouchers_for_run(db, ctx, run.id):
        if v.id in posting_ids or v.base_type in EXCLUDED_BASES or v.status == "CANCELLED":
            continue
        line = MoneyFlowLine(source="VOUCHER", voucher_id=v.id, voucher_number=v.voucher_number, date=v.voucher_date,
                             particulars=f"{v.voucher_type_name}{' - ' + v.party_name if v.party_name else ''}"
                             f"{' - ' + v.narration if v.narration else ''}", amount=v.total_amount,
                             step_id=links.get(v.id) or v.linked_step_id)  # fmt: skip
        (credits if v.base_type in CREDIT_BASES else debits).append(line)
    for ln in lines:
        line = MoneyFlowLine(source=ln.source, voucher_id=ln.voucher_id, voucher_number=None, date=ln.line_date,
                             particulars=ln.particulars, amount=ln.amount, step_id=ln.step_id)  # fmt: skip
        (debits if ln.entry_type == "DR" else credits).append(line)
    total_dr = sum((x.amount for x in debits), ZERO)
    total_cr = sum((x.amount for x in credits), ZERO)
    net = total_dr - total_cr
    accepted = dz(run.accepted_qty)
    unit = q4(net / accepted) if accepted > 0 else ZERO
    return MoneyFlowOut(debits=debits, credits=credits, total_debit=total_dr, total_credit=total_cr, net_cost=net,
                        accepted_qty=accepted, unit_cost=unit)  # fmt: skip


async def recompute(db: AsyncSession, ctx: TenantContext, run: PeriodRun) -> MoneyFlowOut:
    await db.flush()
    flow = await money_flow(db, ctx, run)
    run.total_debit_cost, run.total_credit_recovery = flow.total_debit, flow.total_credit
    run.computed_unit_cost = flow.unit_cost
    await db.flush()
    return flow


async def get_money_flow(db: AsyncSession, ctx: TenantContext, run_id: uuid.UUID) -> MoneyFlowOut:
    run = await get_run(db, ctx, run_id)
    await assert_run_access(ctx, db, run, "READ")
    return await money_flow(db, ctx, run)


async def _check_step(db: AsyncSession, run: PeriodRun, step_id: uuid.UUID | None) -> None:
    if step_id and step_id not in {s.id for s in await get_steps(db, run.id)}:
        raise NotFoundError("Step not found in this run")


async def post_to_run(db: AsyncSession, ctx: TenantContext, run_id: uuid.UUID, body: RunPostingIn) -> RunPostingOut:
    run = await get_run(db, ctx, run_id, lock=True)
    await assert_run_access(ctx, db, run, "WRITE")
    if run.status == "CANCELLED":
        raise ValidationFailedError("Cancelled runs cannot receive postings")
    if body.amount <= 0:
        raise ValidationFailedError("Amount must be greater than zero")
    if body.ledger_id == body.contra_ledger_id:
        raise ValidationFailedError("Ledger and contra ledger must differ")
    await _check_step(db, run, body.step_id)
    other = "CR" if body.entry_type == "DR" else "DR"
    entries = [accounts.SystemEntry(body.ledger_id, body.entry_type, body.amount, run.cost_centre_id),
               accounts.SystemEntry(body.contra_ledger_id, other, body.amount)]  # fmt: skip
    narration = body.narration or f"{'Direct expense' if body.entry_type == 'DR' else 'Recovery'} - {run.run_title}"
    voucher_id = await accounts.post_system_voucher(db, ctx, base_type="JOURNAL", voucher_date=body.voucher_date,
                                                    entries=entries, narration=narration, linked_period_run_id=run.id,
                                                    linked_step_id=body.step_id)  # fmt: skip
    line = PeriodRunCostLine(org_id=ctx.org_id, period_run_id=run.id, step_id=body.step_id, voucher_id=voucher_id,
                             source="POSTING", entry_type=body.entry_type, amount=body.amount,
                             line_date=body.voucher_date, particulars=narration, created_by=ctx.user_id)  # fmt: skip
    db.add(line)
    await db.flush()
    await write_audit(db, ctx, "OPERATIONS", "POST", "period_run", run.id, after={
        "voucher_id": voucher_id, "entry_type": body.entry_type, "amount": body.amount})  # fmt: skip
    return RunPostingOut(voucher_id=voucher_id, money_flow=await recompute(db, ctx, run))


async def link_voucher(db: AsyncSession, ctx: TenantContext, run_id: uuid.UUID, body: LinkVoucherIn) -> MoneyFlowOut:
    run = await get_run(db, ctx, run_id, lock=True)
    await assert_run_access(ctx, db, run, "WRITE")
    await _check_step(db, run, body.step_id)
    await accounts.link_voucher_to_run(db, ctx, voucher_id=body.voucher_id, run_id=run.id, step_id=body.step_id)
    link = (await db.execute(select(PeriodRunVoucherLink).where(
        PeriodRunVoucherLink.period_run_id == run.id, PeriodRunVoucherLink.voucher_id == body.voucher_id))).scalar()  # fmt: skip
    if link is None:
        db.add(PeriodRunVoucherLink(org_id=ctx.org_id, period_run_id=run.id, voucher_id=body.voucher_id,
                                    step_id=body.step_id, linked_by=ctx.user_id))  # fmt: skip
    else:
        link.step_id = body.step_id
    await write_audit(db, ctx, "OPERATIONS", "UPDATE", "period_run", run.id,
                      after={"linked_voucher_id": body.voucher_id, "step_id": body.step_id})  # fmt: skip
    return await recompute(db, ctx, run)


async def unlink_voucher(db: AsyncSession, ctx: TenantContext, run_id: uuid.UUID, voucher_id: uuid.UUID) -> None:
    run = await get_run(db, ctx, run_id, lock=True)
    await assert_run_access(ctx, db, run, "WRITE")
    res = await db.execute(delete(PeriodRunVoucherLink).where(PeriodRunVoucherLink.period_run_id == run.id,
                                                              PeriodRunVoucherLink.voucher_id == voucher_id))  # fmt: skip
    if not res.rowcount:
        raise NotFoundError("This voucher is not linked to the run")
    # shortcut: accounts has no unlink helper; link_voucher_to_run(run_id=None) clears the voucher's run link
    # (requested as Optional in docs/plan/requests/S2.md) — switch when S2 adds unlink_voucher_from_run.
    await accounts.link_voucher_to_run(db, ctx, voucher_id=voucher_id, run_id=None, step_id=None)  # type: ignore[arg-type]
    await write_audit(db, ctx, "OPERATIONS", "DELETE", "period_run_voucher_link", run.id,
                      before={"voucher_id": voucher_id})  # fmt: skip
    await recompute(db, ctx, run)


async def apply_payroll_allocation(db: AsyncSession, ctx: TenantContext, run_id: uuid.UUID, amount: Decimal) -> None:
    run = await get_run(db, ctx, run_id, lock=True)
    if amount == 0:
        return
    db.add(PeriodRunCostLine(org_id=ctx.org_id, period_run_id=run.id, source="PAYROLL",
                             entry_type="DR" if amount > 0 else "CR", amount=abs(amount), line_date=today(),
                             particulars="Allocated direct labour (payroll)", created_by=ctx.user_id))  # fmt: skip
    await write_audit(db, ctx, "OPERATIONS", "UPDATE", "period_run", run.id, after={"payroll_allocation": amount})
    await recompute(db, ctx, run)


async def post_manufacturing_journal(
    db: AsyncSession, ctx: TenantContext, run: PeriodRun, unit_cost: Decimal
) -> uuid.UUID | None:
    """CR raw materials per BOM (valuation = item opening rate), DR FG at unit cost, balance to MFG_OVERHEAD."""
    accepted = dz(run.accepted_qty)
    if run.stock_item_id is None or accepted <= 0:
        return None
    item = await accounts.get_stock_item(db, ctx, run.stock_item_id)
    godowns = await accounts.get_system_godown_ids(db, ctx)
    inventory, rm_value = [], ZERO
    for comp in item.bom_components or []:
        raw_id = uuid.UUID(str(comp["raw_item_id"]))
        qty = q4(Decimal(str(comp.get("qty_per_unit") or 0)) * run.planned_qty
                 * (1 + Decimal(str(comp.get("scrap_pct") or 0)) / 100))  # fmt: skip
        rate = dz((await accounts.get_stock_item(db, ctx, raw_id)).opening_rate)
        if qty > 0:
            amount = q4(qty * rate)
            rm_value += amount
            inventory.append(accounts.SystemInventory(raw_id, godowns["MAIN"], "OUTWARD", qty, rate, amount))
    fg_value = q4(accepted * unit_cost) if unit_cost > 0 else rm_value
    ledgers = await accounts.get_ledger_ids_by_code(db, ctx, ["STOCK_FG", "STOCK_RM", "MFG_OVERHEAD"])
    entries = []
    if fg_value > 0:
        entries.append(accounts.SystemEntry(ledgers["STOCK_FG"], "DR", fg_value, run.cost_centre_id))
    if rm_value > 0:
        entries.append(accounts.SystemEntry(ledgers["STOCK_RM"], "CR", rm_value, run.cost_centre_id))
    diff = fg_value - rm_value
    if diff != 0:
        entries.append(accounts.SystemEntry(ledgers["MFG_OVERHEAD"], "CR" if diff > 0 else "DR", abs(diff),
                                            run.cost_centre_id))  # fmt: skip
    if not entries and not inventory:
        return None
    return await accounts.post_system_voucher(db, ctx, base_type="MFG_JOURNAL", voucher_date=today(), entries=entries,
                                              inventory=inventory, narration=f"Manufacturing journal - {run.run_title}",
                                              linked_period_run_id=run.id)  # fmt: skip
