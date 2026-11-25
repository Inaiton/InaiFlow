"""Period runs: creation (snapshot + steps + cost centre + folder), lifecycle, step execution and routing."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import write_audit
from app.core.context import TenantContext
from app.core.errors import (
    InstrumentExpiredError,
    InvalidStateError,
    NotFoundError,
    QtyMismatchError,
    StepLockedError,
    StepNotActiveError,
    ValidationFailedError,
)
from app.core.fy import month_start
from app.core.money import q2, q4
from app.core.pagination import PageParams, paginate
from app.core.sequences import format_number, next_value
from app.modules.accounts import interface as accounts
from app.modules.documents import interface as documents
from app.modules.operations import graph as g
from app.modules.operations import qc
from app.modules.operations.common import (
    ZERO,
    assert_run_access,
    dz,
    get_run,
    get_steps,
    get_workflow,
    item_names,
    now,
    run_scope,
    today,
    user_names,
)
from app.modules.operations.models import (
    CalibrationInstrument,
    IsoNcrCapaRecord,
    PeriodRun,
    PeriodRunStep,
    WorkflowTemplate,
)
from app.modules.operations.schemas import (
    NcrOut,
    OptionalReasonIn,
    ReasonIn,
    RunCreateIn,
    RunOut,
    RunSummary,
    StepExecuteIn,
    StepExecuteOut,
    StepOut,
)

DONE_STATES = ("PASSED", "SKIPPED", "LOCKED", "REJECTED")
OPEN_RUN_STATES = ("PLANNED", "IN_PROGRESS", "QC_HOLD")


# ---------------------------------------------------------------- step math (pure on ORM rows)
def has_rework_edge(graph: dict[str, Any], node_id: str) -> bool:
    return g.rework_target(graph, node_id) is not None


def pending(step: PeriodRunStep, graph: dict[str, Any]) -> Decimal:
    sent_rework = dz(step.rework_qty) if has_rework_edge(graph, step.node_id) else ZERO
    return dz(step.input_qty) - dz(step.accepted_qty) - dz(step.rejected_qty) - sent_rework


def settle_status(step: PeriodRunStep, graph: dict[str, Any]) -> None:
    if pending(step, graph) > 0:
        step.status = "ACTIVE"
    elif dz(step.accepted_qty) == 0 and dz(step.rejected_qty) > 0:
        step.status = "REJECTED"
    elif step.status != "SKIPPED":
        step.status = "PASSED"
    if step.is_locked and step.node_shape == "DIAMOND" and step.status in ("PASSED", "REJECTED"):
        step.status = "LOCKED"


def _receive(step: PeriodRunStep, qty: Decimal) -> None:
    step.input_qty = dz(step.input_qty) + qty
    step.status = "ACTIVE"


# ---------------------------------------------------------------- out builders
def _yield(run: PeriodRun) -> Decimal | None:
    if not run.planned_qty:
        return None
    return q2(dz(run.accepted_qty) * 100 / run.planned_qty)


def _progress(steps: list[PeriodRunStep], run: PeriodRun) -> Decimal:
    if run.status == "COMPLETED":
        return Decimal("100")
    if not steps:
        return ZERO
    done = sum(1 for s in steps if s.status in DONE_STATES)
    return q2(Decimal(done) * 100 / len(steps))


async def summaries(db: AsyncSession, ctx: TenantContext, runs: list[PeriodRun]) -> list[RunSummary]:
    if not runs:
        return []
    ids = [r.id for r in runs]
    wf_rows = await db.execute(select(WorkflowTemplate.id, WorkflowTemplate.name).where(
        WorkflowTemplate.id.in_({r.workflow_template_id for r in runs})))  # fmt: skip
    wf_names = dict(wf_rows.all())
    steps_by_run: dict[uuid.UUID, list[PeriodRunStep]] = {i: [] for i in ids}
    for s in (await db.execute(select(PeriodRunStep).where(PeriodRunStep.period_run_id.in_(ids))
                               .order_by(PeriodRunStep.sequence))).scalars():  # fmt: skip
        steps_by_run[s.period_run_id].append(s)
    names = await item_names(db, ctx, [r.stock_item_id for r in runs])
    return [
        RunSummary(id=r.id, run_title=r.run_title, period_month=r.period_month, status=r.status,
                   planned_qty=r.planned_qty, accepted_qty=dz(r.accepted_qty), rejected_qty=dz(r.rejected_qty),
                   rework_qty=dz(r.rework_qty), yield_pct=_yield(r), computed_unit_cost=dz(r.computed_unit_cost),
                   stock_item_id=r.stock_item_id, stock_item_name=names.get(r.stock_item_id) if r.stock_item_id else None,
                   workflow_id=r.workflow_template_id, workflow_name=wf_names.get(r.workflow_template_id, ""),
                   workflow_version=r.workflow_version,
                   current_step_names=[s.step_name for s in steps_by_run[r.id] if s.status == "ACTIVE"],
                   progress_pct=_progress(steps_by_run[r.id], r), created_at=r.created_at)
        for r in runs
    ]  # fmt: skip


async def ncr_outs(db: AsyncSession, ncrs: list[IsoNcrCapaRecord]) -> list[NcrOut]:
    if not ncrs:
        return []
    run_ids = {n.period_run_id for n in ncrs if n.period_run_id}
    step_ids = {n.run_step_id for n in ncrs if n.run_step_id}
    titles = (
        dict((await db.execute(select(PeriodRun.id, PeriodRun.run_title).where(PeriodRun.id.in_(run_ids)))).all())
        if run_ids
        else {}
    )
    steps = (
        dict(
            (
                await db.execute(
                    select(PeriodRunStep.id, PeriodRunStep.step_name).where(PeriodRunStep.id.in_(step_ids))
                )
            ).all()
        )
        if step_ids
        else {}
    )
    names = await user_names(db, [n.assigned_to for n in ncrs] + [n.closed_by for n in ncrs])
    return [
        NcrOut(id=n.id, ncr_number=n.ncr_number, period_run_id=n.period_run_id, run_title=titles.get(n.period_run_id),
               run_step_id=n.run_step_id, step_name=steps.get(n.run_step_id), rejected_qty=n.rejected_qty,
               defect_description=n.defect_description, root_cause_analysis=n.root_cause_analysis,
               corrective_action=n.corrective_action, preventive_action=n.preventive_action,
               verification_notes=n.verification_notes, source=n.source, status=n.status, assigned_to=n.assigned_to,
               assigned_to_name=names.get(n.assigned_to) if n.assigned_to else None,
               closed_by_name=names.get(n.closed_by) if n.closed_by else None, closed_at=n.closed_at,
               created_at=n.created_at)
        for n in ncrs
    ]  # fmt: skip


async def step_outs(db: AsyncSession, ctx: TenantContext, steps: list[PeriodRunStep]) -> list[StepOut]:
    if not steps:
        return []
    ids = [s.id for s in steps]
    ncr_rows = await db.execute(select(IsoNcrCapaRecord.run_step_id, IsoNcrCapaRecord.id)
                                .where(IsoNcrCapaRecord.run_step_id.in_(ids))
                                .order_by(IsoNcrCapaRecord.created_at))  # fmt: skip
    ncr_by_step = dict(ncr_rows.all())
    attachments = await documents.count_documents_by_steps(db, ctx, ids)
    names = await user_names(db, [s.executed_by for s in steps] + [s.signed_off_by for s in steps])
    out = []
    for s in steps:
        readings = {k: {"value": v.get("value"), "in_tolerance": v.get("in_tolerance"),
                        "auto_filled": bool(v.get("auto_filled"))} for k, v in (s.qc_measurements or {}).items()}  # fmt: skip
        out.append(StepOut(
            id=s.id, node_id=s.node_id, step_name=s.step_name, node_shape=s.node_shape, sequence=s.sequence,
            status=s.status, input_qty=dz(s.input_qty), accepted_qty=dz(s.accepted_qty),
            rejected_qty=dz(s.rejected_qty), rework_qty=dz(s.rework_qty), qc_measurements=readings,
            branch_taken=s.branch_taken, quick_qc=s.quick_qc, is_locked=s.is_locked,
            executed_by_name=names.get(s.executed_by) if s.executed_by else None, executed_at=s.executed_at,
            signed_off_by_name=names.get(s.signed_off_by) if s.signed_off_by else None,
            signed_off_at=s.signed_off_at, override_reason=s.override_reason, skip_reason=s.skip_reason,
            notes=s.notes, instrument_id=s.instrument_id, ncr_id=ncr_by_step.get(s.id),
            attachment_count=attachments.get(s.id, 0)))  # fmt: skip
    return out


async def run_out(db: AsyncSession, ctx: TenantContext, run: PeriodRun) -> RunOut:
    from app.modules.operations import service_money as money

    await db.flush()
    await db.refresh(run)
    summary = (await summaries(db, ctx, [run]))[0]
    steps = await get_steps(db, run.id)
    names = await user_names(db, [run.created_by])
    return RunOut(**summary.model_dump(), graph_snapshot=run.graph_snapshot, steps=await step_outs(db, ctx, steps),
                  money_flow=await money.money_flow(db, ctx, run), cost_centre_id=run.cost_centre_id,
                  doc_folder_id=run.doc_folder_id, hold_reason=run.hold_reason, cancel_reason=run.cancel_reason,
                  started_at=run.started_at, completed_at=run.completed_at,
                  created_by_name=names.get(run.created_by, ""))  # fmt: skip


# ---------------------------------------------------------------- queries
def _list_stmt(ctx: TenantContext) -> Select[Any]:
    return select(PeriodRun).where(PeriodRun.org_id == ctx.org_id)


async def list_runs(
    db: AsyncSession, ctx: TenantContext, page: PageParams, *, status: str | None, stock_item_id: uuid.UUID | None,
    period_month: str | None, q: str | None,
) -> tuple[list[RunSummary], int]:  # fmt: skip
    from app.core.fy import parse_month

    scope = await run_scope(ctx, db)
    stmt = _list_stmt(ctx).where(scope.clause())
    if status:
        stmt = stmt.where(PeriodRun.status == status)
    if stock_item_id:
        stmt = stmt.where(PeriodRun.stock_item_id == stock_item_id)
    if period_month:
        try:
            stmt = stmt.where(PeriodRun.period_month == parse_month(period_month))
        except ValueError:
            raise ValidationFailedError("period_month must be YYYY-MM") from None
    if q:
        stmt = stmt.where(PeriodRun.run_title.ilike(f"%{q.strip()}%"))
    rows, total = await paginate(db, stmt.order_by(PeriodRun.created_at.desc()), page)
    return await summaries(db, ctx, [r[0] for r in rows]), total


async def runs_for_item(db: AsyncSession, ctx: TenantContext, item_id: uuid.UUID) -> list[RunSummary]:
    scope = await run_scope(ctx, db)
    stmt = _list_stmt(ctx).where(PeriodRun.stock_item_id == item_id, scope.clause())
    return await summaries(db, ctx, list((await db.execute(stmt.order_by(PeriodRun.created_at.desc()))).scalars()))


async def get_run_out(db: AsyncSession, ctx: TenantContext, run_id: uuid.UUID) -> RunOut:
    run = await get_run(db, ctx, run_id)
    await assert_run_access(ctx, db, run, "READ")
    return await run_out(db, ctx, run)


# ---------------------------------------------------------------- create & lifecycle
def _default_title(base: str, month: date) -> str:
    return f"{base} - {month.strftime('%b %Y')}"


def _activate_starts(run: PeriodRun, steps: list[PeriodRunStep]) -> None:
    starts = set(g.start_nodes(run.graph_snapshot))
    for s in steps:
        if s.node_id in starts:
            s.input_qty, s.status = run.planned_qty, "ACTIVE"
    run.status, run.started_at = "IN_PROGRESS", now()


async def create_run(db: AsyncSession, ctx: TenantContext, body: RunCreateIn) -> RunOut:
    wf = await get_workflow(db, ctx, body.workflow_id)
    if wf.status != "PUBLISHED":
        raise InvalidStateError("Runs can only be created from a published workflow version")
    if body.planned_qty <= 0:
        raise ValidationFailedError("Planned quantity must be greater than zero")
    item_id = body.stock_item_id or wf.stock_item_id
    names = await item_names(db, ctx, [item_id]) if item_id else {}
    if item_id and item_id not in names:
        raise NotFoundError("Stock item not found")
    month = month_start(body.period_month)
    title = (body.run_title or "").strip() or _default_title(names.get(item_id) or wf.name, month)
    graph = wf.graph_definition
    run = PeriodRun(org_id=ctx.org_id, workflow_template_id=wf.id, workflow_version=wf.version, graph_snapshot=graph,
                    stock_item_id=item_id, run_title=title, period_month=month, planned_qty=body.planned_qty,
                    status="PLANNED", created_by=ctx.user_id)  # fmt: skip
    db.add(run)
    await db.flush()
    nodes = g.node_map(graph)
    steps = []
    for seq, nid in enumerate(g.topological_order(graph), start=1):
        node = nodes[nid]
        steps.append(PeriodRunStep(org_id=ctx.org_id, period_run_id=run.id, node_id=nid,
                                   step_name=node.get("label") or nid, node_shape=node["shape"], sequence=seq,
                                   input_qty=ZERO, accepted_qty=ZERO, rejected_qty=ZERO, rework_qty=ZERO,
                                   qc_measurements={}, status="PENDING"))  # fmt: skip
    db.add_all(steps)
    if body.start_now is not False:
        _activate_starts(run, steps)
    run.cost_centre_id = await accounts.create_cost_centre(db, ctx, name=title, linked_period_run_id=run.id)
    run.doc_folder_id = await documents.create_run_folder(db, ctx, run_id=run.id, run_title=title, month=month)
    await db.flush()
    await write_audit(db, ctx, "OPERATIONS", "CREATE", "period_run", run.id, after=run.to_dict())
    return await run_out(db, ctx, run)


async def _transition(
    db: AsyncSession, ctx: TenantContext, run_id: uuid.UUID, allowed: tuple[str, ...], level: str = "WRITE"
) -> PeriodRun:
    run = await get_run(db, ctx, run_id, lock=True)
    await assert_run_access(ctx, db, run, level)
    if run.status not in allowed:
        raise InvalidStateError(f"Not allowed while the run is {run.status}")
    return run


async def _audit_status(db: AsyncSession, ctx: TenantContext, run: PeriodRun, before: str, reason: str | None) -> None:
    await write_audit(db, ctx, "OPERATIONS", "TRANSITION", "period_run", run.id, before={"status": before},
                      after={"status": run.status}, reason=reason)  # fmt: skip


async def start_run(db: AsyncSession, ctx: TenantContext, run_id: uuid.UUID) -> RunOut:
    run = await _transition(db, ctx, run_id, ("PLANNED",))
    _activate_starts(run, await get_steps(db, run.id, lock=True))
    await _audit_status(db, ctx, run, "PLANNED", None)
    return await run_out(db, ctx, run)


async def hold_run(db: AsyncSession, ctx: TenantContext, run_id: uuid.UUID, body: ReasonIn) -> RunOut:
    run = await _transition(db, ctx, run_id, ("IN_PROGRESS",))
    run.status, run.hold_reason = "QC_HOLD", body.reason
    await _audit_status(db, ctx, run, "IN_PROGRESS", body.reason)
    return await run_out(db, ctx, run)


async def resume_run(db: AsyncSession, ctx: TenantContext, run_id: uuid.UUID) -> RunOut:
    run = await _transition(db, ctx, run_id, ("QC_HOLD",))
    run.status, run.hold_reason = "IN_PROGRESS", None
    await _audit_status(db, ctx, run, "QC_HOLD", None)
    return await run_out(db, ctx, run)


async def cancel_run(db: AsyncSession, ctx: TenantContext, run_id: uuid.UUID, body: ReasonIn) -> RunOut:
    run = await _transition(db, ctx, run_id, OPEN_RUN_STATES, "FULL")
    before = run.status
    run.status, run.cancel_reason = "CANCELLED", body.reason
    await write_audit(db, ctx, "OPERATIONS", "CANCEL", "period_run", run.id, before={"status": before},
                      after={"status": "CANCELLED"}, reason=body.reason)  # fmt: skip
    return await run_out(db, ctx, run)


async def complete_run(db: AsyncSession, ctx: TenantContext, run_id: uuid.UUID) -> RunOut:
    from app.modules.operations import service_money as money

    run = await _transition(db, ctx, run_id, ("IN_PROGRESS",), "FULL")
    steps = await get_steps(db, run.id, lock=True)
    open_steps = [s.step_name for s in steps if (dz(s.input_qty) > 0 or s.status != "PENDING")
                  and (s.status not in DONE_STATES or pending(s, run.graph_snapshot) > 0)]  # fmt: skip
    if open_steps:
        raise InvalidStateError("Every reached step must be passed, skipped or locked", {"open_steps": open_steps})
    flow = await money.recompute(db, ctx, run)
    run.computed_unit_cost = flow.unit_cost
    run.mfg_voucher_id = await money.post_manufacturing_journal(db, ctx, run, flow.unit_cost)
    run.status, run.completed_at = "COMPLETED", now()
    await _audit_status(db, ctx, run, "IN_PROGRESS", None)
    return await run_out(db, ctx, run)


# ---------------------------------------------------------------- step execution
@dataclass
class _Effects:
    activated: list[uuid.UUID] = field(default_factory=list)
    ncr: IsoNcrCapaRecord | None = None
    stock_voucher_id: uuid.UUID | None = None


async def _load_for_step(
    db: AsyncSession, ctx: TenantContext, run_id: uuid.UUID, step_id: uuid.UUID
) -> tuple[PeriodRun, list[PeriodRunStep], PeriodRunStep]:
    run = await get_run(db, ctx, run_id, lock=True)
    await assert_run_access(ctx, db, run, "WRITE")
    steps = await get_steps(db, run.id, lock=True)
    step = next((s for s in steps if s.id == step_id), None)
    if step is None:
        raise NotFoundError("Step not found")
    return run, steps, step


def _assert_executable(ctx: TenantContext, run: PeriodRun, step: PeriodRunStep, override_reason: str | None) -> bool:
    """Returns True when this is a locked-step override."""
    if run.status != "IN_PROGRESS":
        raise InvalidStateError(f"Steps cannot be executed while the run is {run.status}")
    override = False
    if step.is_locked:
        if not (ctx.has("operations.qc_signoff", "FULL") and (override_reason or "").strip()):
            raise StepLockedError()
        override = True
    if step.status == "PENDING" or pending(step, run.graph_snapshot) <= 0:
        raise StepNotActiveError()
    return override


async def _instrument_guard(db: AsyncSession, ctx: TenantContext, instrument_id: uuid.UUID | None) -> None:
    if instrument_id is None:
        return
    inst = await db.get(CalibrationInstrument, instrument_id)
    if inst is None or inst.org_id != ctx.org_id:
        raise NotFoundError("Instrument not found")
    if inst.status == "EXPIRED" or inst.next_due_date < today():
        raise InstrumentExpiredError(details={"instrument_code": inst.instrument_code,
                                              "next_due_date": inst.next_due_date.isoformat()})  # fmt: skip


async def _stock_rate(db: AsyncSession, ctx: TenantContext, item_id: uuid.UUID) -> Decimal:
    item = await accounts.get_stock_item(db, ctx, item_id)
    return dz(item.opening_rate)


async def _stock_journal(
    db: AsyncSession, ctx: TenantContext, run: PeriodRun, step: PeriodRunStep, qty: Decimal, to: str, narration: str
) -> uuid.UUID | None:
    if run.stock_item_id is None or qty <= 0:
        return None
    godowns = await accounts.get_system_godown_ids(db, ctx)
    rate = await _stock_rate(db, ctx, run.stock_item_id)
    amount = q4(qty * rate)
    inv = [accounts.SystemInventory(run.stock_item_id, godowns["WIP"], "OUTWARD", qty, rate, amount),
           accounts.SystemInventory(run.stock_item_id, godowns[to], "INWARD", qty, rate, amount)]  # fmt: skip
    return await accounts.post_system_voucher(db, ctx, base_type="STOCK_JOURNAL", voucher_date=today(), entries=[],
                                              inventory=inv, narration=narration, linked_period_run_id=run.id,
                                              linked_step_id=step.id)  # fmt: skip


async def create_ncr(
    db: AsyncSession, ctx: TenantContext, *, run_id: uuid.UUID | None, step_id: uuid.UUID | None, qty: Decimal,
    description: str, source: str, assigned_to: uuid.UUID | None = None,
) -> IsoNcrCapaRecord:  # fmt: skip
    year = today().year
    n = await next_value(db, ctx.org_id, f"NCR-{year}")
    ncr = IsoNcrCapaRecord(org_id=ctx.org_id, ncr_number=format_number(f"NCR-{year}-", n, 4), period_run_id=run_id,
                           run_step_id=step_id, rejected_qty=qty, defect_description=description, source=source,
                           status="OPEN", assigned_to=assigned_to, created_at=now())  # fmt: skip
    db.add(ncr)
    await db.flush()
    await write_audit(db, ctx, "OPERATIONS", "CREATE", "ncr", ncr.id, after=ncr.to_dict())
    return ncr


def _aggregate(run: PeriodRun, steps: list[PeriodRunStep]) -> None:
    run.accepted_qty = sum((dz(s.accepted_qty) for s in steps if s.node_shape == "TERMINATOR"), ZERO)
    run.rejected_qty = sum((dz(s.rejected_qty) for s in steps), ZERO)
    run.rework_qty = sum((dz(s.rework_qty) for s in steps), ZERO)


async def _route(
    db: AsyncSession, ctx: TenantContext, run: PeriodRun, steps: list[PeriodRunStep], step: PeriodRunStep,
    accepted: Decimal, rejected: Decimal, rework: Decimal, defect: str | None,
) -> _Effects:  # fmt: skip
    graph = run.graph_snapshot
    by_node = {s.node_id: s for s in steps}
    fx = _Effects()

    def send(node_id: str, qty: Decimal) -> None:
        target = by_node.get(node_id)
        if target is not None and qty > 0:
            _receive(target, qty)
            if target.id not in fx.activated:
                fx.activated.append(target.id)

    if accepted > 0:
        if step.node_shape == "TERMINATOR":
            fx.stock_voucher_id = await _stock_journal(db, ctx, run, step, accepted, "FG",
                                                       f"{run.run_title}: {accepted} units to finished goods")  # fmt: skip
        else:
            for t in g.pass_targets(graph, step.node_id):
                send(t, accepted)
    if rework > 0:
        target = g.rework_target(graph, step.node_id)
        if target:
            send(target, rework)
    if rejected > 0:
        scrap_id = await _stock_journal(db, ctx, run, step, rejected, "SCRAP",
                                        f"{run.run_title}: {rejected} units rejected at {step.step_name}")  # fmt: skip
        fx.stock_voucher_id = fx.stock_voucher_id or scrap_id
        fx.ncr = await create_ncr(db, ctx, run_id=run.id, step_id=step.id, qty=rejected, source="AUTO_QC",
                                  description=(defect or "").strip()
                                  or f"{rejected} units rejected at {step.step_name}")  # fmt: skip
        for t in g.reject_targets(graph, step.node_id):
            send(t, rejected)
    settle_status(step, graph)
    _aggregate(run, steps)
    return fx


async def _execute_out(
    db: AsyncSession, ctx: TenantContext, run: PeriodRun, step: PeriodRunStep, fx: _Effects
) -> StepExecuteOut:
    await db.flush()
    await db.refresh(step)
    return StepExecuteOut(step=(await step_outs(db, ctx, [step]))[0], run=(await summaries(db, ctx, [run]))[0],
                          activated_step_ids=fx.activated, ncr=(await ncr_outs(db, [fx.ncr]))[0] if fx.ncr else None,
                          stock_voucher_id=fx.stock_voucher_id)  # fmt: skip


def _record(step: PeriodRunStep, ctx: TenantContext, a: Decimal, r: Decimal, w: Decimal) -> None:
    step.accepted_qty = dz(step.accepted_qty) + a
    step.rejected_qty = dz(step.rejected_qty) + r
    step.rework_qty = dz(step.rework_qty) + w
    step.executed_by, step.executed_at = ctx.user_id, now()


async def execute_step(
    db: AsyncSession, ctx: TenantContext, run_id: uuid.UUID, step_id: uuid.UUID, body: StepExecuteIn
) -> StepExecuteOut:
    run, steps, step = await _load_for_step(db, ctx, run_id, step_id)
    override = _assert_executable(ctx, run, step, body.override_reason)
    a, r, w, inp = body.accepted_qty, body.rejected_qty, body.rework_qty or ZERO, body.input_qty
    if min(a, r, w) < 0 or inp <= 0:
        raise ValidationFailedError("Quantities must be positive")
    if a + r + w != inp:
        raise QtyMismatchError("accepted + rejected + rework must equal input",
                               {"input_qty": str(inp), "sum": str(a + r + w)})  # fmt: skip
    available = pending(step, run.graph_snapshot)
    if inp > available:
        raise QtyMismatchError("Input exceeds the quantity available at this step", {"available": str(available)})
    await _instrument_guard(db, ctx, body.instrument_id)
    node = g.node_map(run.graph_snapshot).get(step.node_id, {})
    cfg = g.config_of(node)
    fields = cfg.get("qc_fields") or []
    try:
        readings = qc.build_readings(fields, body.measurements, quick_qc=bool(body.quick_qc))
    except qc.ReadingError as exc:
        raise ValidationFailedError(str(exc), {"field": exc.field}) from None
    if step.node_shape == "DIAMOND":
        try:
            passed = qc.evaluate_pass_criteria(cfg.get("pass_criteria"), readings, qc_fields=fields, accepted=a,
                                               rejected=r, rework=w, input_qty=inp)  # fmt: skip
        except qc.ExpressionError as exc:
            raise ValidationFailedError(f"Pass criteria cannot be evaluated: {exc}") from None
        if not passed and a > 0:
            raise ValidationFailedError("QC readings do not meet the pass criteria; units cannot be accepted",
                                        {"criteria": "FAILED", "readings": readings})  # fmt: skip
    before = step.to_dict()
    _record(step, ctx, a, r, w)
    step.qc_measurements = {**(step.qc_measurements or {}), **readings}
    step.quick_qc = bool(body.quick_qc) or any(x["auto_filled"] for x in readings.values())
    step.branch_taken = "PASS" if a > 0 else ("REJECT" if r > 0 else "REWORK")
    step.instrument_id = body.instrument_id or step.instrument_id
    step.notes = body.notes if body.notes is not None else step.notes
    if override:
        step.override_reason = body.override_reason
        await write_audit(db, ctx, "OPERATIONS", "OVERRIDE", "period_run_step", step.id,
                          before={"is_locked": True}, after={"executed": True}, reason=body.override_reason)  # fmt: skip
    fx = await _route(db, ctx, run, steps, step, a, r, w, body.defect_description)
    await write_audit(db, ctx, "OPERATIONS", "EXECUTE", "period_run_step", step.id, before=before,
                      after=step.to_dict(), changed_only=True)  # fmt: skip
    return await _execute_out(db, ctx, run, step, fx)


async def skip_step(
    db: AsyncSession, ctx: TenantContext, run_id: uuid.UUID, step_id: uuid.UUID, body: ReasonIn
) -> StepExecuteOut:
    run, steps, step = await _load_for_step(db, ctx, run_id, step_id)
    _assert_executable(ctx, run, step, None)
    node = g.node_map(run.graph_snapshot).get(step.node_id, {})
    if step.node_shape == "TERMINATOR" or g.config_of(node).get("skippable") is False:
        raise InvalidStateError("This step cannot be skipped")
    qty = pending(step, run.graph_snapshot)
    _record(step, ctx, qty, ZERO, ZERO)
    step.status, step.skip_reason, step.branch_taken = "SKIPPED", body.reason, "PASS"
    fx = await _route(db, ctx, run, steps, step, qty, ZERO, ZERO, None)
    step.status = "SKIPPED"
    await write_audit(db, ctx, "OPERATIONS", "EXECUTE", "period_run_step", step.id, after={"status": "SKIPPED",
                      "passed_qty": qty}, reason=body.reason)  # fmt: skip
    return await _execute_out(db, ctx, run, step, fx)


async def succeed_step(
    db: AsyncSession, ctx: TenantContext, run_id: uuid.UUID, step_id: uuid.UUID, body: OptionalReasonIn
) -> StepExecuteOut:
    run, steps, step = await _load_for_step(db, ctx, run_id, step_id)
    override = _assert_executable(ctx, run, step, body.reason)
    qty = pending(step, run.graph_snapshot)
    fields = g.config_of(g.node_map(run.graph_snapshot).get(step.node_id, {})).get("qc_fields") or []
    _record(step, ctx, qty, ZERO, ZERO)
    step.qc_measurements = {**(step.qc_measurements or {}), **qc.nominal_readings(fields)}
    step.quick_qc, step.branch_taken = True, "PASS"
    if body.reason:
        step.notes = body.reason
    if override:
        step.override_reason = body.reason
        await write_audit(db, ctx, "OPERATIONS", "OVERRIDE", "period_run_step", step.id,
                          before={"is_locked": True}, after={"succeeded": True}, reason=body.reason)  # fmt: skip
    fx = await _route(db, ctx, run, steps, step, qty, ZERO, ZERO, None)
    await write_audit(db, ctx, "OPERATIONS", "EXECUTE", "period_run_step", step.id,
                      after={"status": step.status, "succeeded_qty": qty}, reason=body.reason)  # fmt: skip
    return await _execute_out(db, ctx, run, step, fx)


async def signoff_step(db: AsyncSession, ctx: TenantContext, run_id: uuid.UUID, step_id: uuid.UUID) -> StepOut:
    run, _steps, step = await _load_for_step(db, ctx, run_id, step_id)
    if step.status == "PENDING":
        raise InvalidStateError("Only executed steps can be signed off")
    if step.is_locked:
        raise InvalidStateError("This step is already signed off")
    step.is_locked, step.signed_off_by, step.signed_off_at = True, ctx.user_id, now()
    if step.node_shape == "DIAMOND" and pending(step, run.graph_snapshot) <= 0:
        step.status = "LOCKED"
    await write_audit(db, ctx, "OPERATIONS", "SIGNOFF", "period_run_step", step.id,
                      after={"is_locked": True, "status": step.status})  # fmt: skip
    await db.flush()
    return (await step_outs(db, ctx, [step]))[0]


async def reopen_step(
    db: AsyncSession, ctx: TenantContext, run_id: uuid.UUID, step_id: uuid.UUID, body: ReasonIn
) -> StepOut:
    run, _steps, step = await _load_for_step(db, ctx, run_id, step_id)
    if not step.is_locked:
        raise InvalidStateError("This step is not locked")
    before = {"is_locked": True, "status": step.status, "signed_off_by": step.signed_off_by}
    step.is_locked, step.signed_off_by, step.signed_off_at, step.override_reason = False, None, None, body.reason
    if step.status == "LOCKED":
        step.status = "PASSED"
        settle_status(step, run.graph_snapshot)
    await write_audit(db, ctx, "OPERATIONS", "OVERRIDE", "period_run_step", step.id, before=before,
                      after={"is_locked": False, "status": step.status}, reason=body.reason)  # fmt: skip
    await db.flush()
    return (await step_outs(db, ctx, [step]))[0]


# ---------------------------------------------------------------- stats helpers (items facade, interface)
async def item_stats(
    db: AsyncSession, ctx: TenantContext, item_ids: list[uuid.UUID]
) -> dict[uuid.UUID, dict[str, Any]]:
    if not item_ids:
        return {}
    rows = (await db.execute(select(PeriodRun).where(PeriodRun.org_id == ctx.org_id,
                                                     PeriodRun.stock_item_id.in_(item_ids),
                                                     PeriodRun.status != "CANCELLED"))).scalars()  # fmt: skip
    wf_counts = dict((await db.execute(
        select(WorkflowTemplate.stock_item_id, func.count(func.distinct(WorkflowTemplate.template_key)))
        .where(WorkflowTemplate.org_id == ctx.org_id, WorkflowTemplate.stock_item_id.in_(item_ids))
        .group_by(WorkflowTemplate.stock_item_id))).all())  # fmt: skip
    out: dict[uuid.UUID, dict[str, Any]] = {
        i: {"run_count": 0, "active_run_count": 0, "last_run_at": None, "_y": [], "_c": [],
            "workflow_count": int(wf_counts.get(i, 0))} for i in item_ids}  # fmt: skip
    for r in rows:
        st = out[r.stock_item_id]
        st["run_count"] += 1
        st["active_run_count"] += r.status in OPEN_RUN_STATES
        st["last_run_at"] = max(filter(None, [st["last_run_at"], r.created_at]))
        if r.status == "COMPLETED":
            if (y := _yield(r)) is not None:
                st["_y"].append(y)
            st["_c"].append(dz(r.computed_unit_cost))
    for st in out.values():
        ys, cs = st.pop("_y"), st.pop("_c")
        st["avg_yield_pct"] = q2(sum(ys) / len(ys)) if ys else None
        st["avg_unit_cost"] = q4(sum(cs) / len(cs)) if cs else None
    return out


def any_of(*conds: Any) -> Any:
    return or_(*conds)
