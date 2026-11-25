"""Public API of the operations module (binding signatures, plan §3.6).

S1: ``seed_org_operations``, ``resource_names``, ``refresh_calibration_statuses`` (cron, per org).
S4: run/step queries for payroll and accounts reports, payroll allocation, ``refresh_instrument_statuses``.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import case, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import TenantContext
from app.core.fy import add_months, month_start
from app.modules.operations.models import CalibrationInstrument, PeriodRun, PeriodRunStep
from app.modules.operations.seeding import seed_org_operations
from app.modules.organization import interface as organization

DUE_SOON_DAYS = 30  # keep in sync with service_iso.DUE_SOON_DAYS


def _status_expr(today: date):  # noqa: ANN202
    return case(
        (CalibrationInstrument.next_due_date < today, "EXPIRED"),
        (CalibrationInstrument.next_due_date <= today + timedelta(days=DUE_SOON_DAYS), "DUE_SOON"),
        else_="VALID",
    )


async def resource_names(
    db: AsyncSession, ctx: TenantContext, resource_type: str, ids: list[uuid.UUID]
) -> dict[uuid.UUID, str]:
    if resource_type != "PERIOD_RUN" or not ids:
        return {}
    rows = await db.execute(
        select(PeriodRun.id, PeriodRun.run_title).where(PeriodRun.org_id == ctx.org_id, PeriodRun.id.in_(ids))
    )
    return {i: n for i, n in rows.all()}


async def refresh_calibration_statuses(db: AsyncSession, ctx: TenantContext, today: date) -> int:
    """VALID / DUE_SOON (<= 30 days) / EXPIRED (< today). Returns rows whose status changed."""
    new_status = _status_expr(today)
    res = await db.execute(
        update(CalibrationInstrument)
        .where(CalibrationInstrument.org_id == ctx.org_id, CalibrationInstrument.status != new_status)
        .values(status=new_status)
    )
    return int(res.rowcount or 0)


# ---------------------------------------------------------------- S4 implementations
@dataclass(frozen=True, slots=True)
class RunBrief:
    id: uuid.UUID
    run_title: str
    period_month: date
    status: str
    stock_item_id: uuid.UUID | None
    cost_centre_id: uuid.UUID | None
    doc_folder_id: uuid.UUID | None
    planned_qty: Decimal
    accepted_qty: Decimal
    rejected_qty: Decimal
    rework_qty: Decimal
    total_debit_cost: Decimal
    total_credit_recovery: Decimal
    computed_unit_cost: Decimal
    workflow_template_id: uuid.UUID
    workflow_version: int
    started_at: datetime | None
    completed_at: datetime | None


@dataclass(frozen=True, slots=True)
class StepExecutionDTO:
    period_run_id: uuid.UUID
    run_title: str
    step_id: uuid.UUID
    step_name: str
    node_shape: str
    executed_by: uuid.UUID | None
    executed_at: datetime | None
    input_qty: Decimal
    accepted_qty: Decimal
    rejected_qty: Decimal
    rework_qty: Decimal


def _brief(r: PeriodRun) -> RunBrief:
    z = Decimal(0)
    return RunBrief(r.id, r.run_title, r.period_month, r.status, r.stock_item_id, r.cost_centre_id, r.doc_folder_id,
                    r.planned_qty, r.accepted_qty or z, r.rejected_qty or z, r.rework_qty or z,
                    r.total_debit_cost or z, r.total_credit_recovery or z, r.computed_unit_cost or z,
                    r.workflow_template_id, r.workflow_version, r.started_at, r.completed_at)  # fmt: skip


async def get_runs_by_ids(db: AsyncSession, ctx: TenantContext, run_ids: list[uuid.UUID]) -> list[RunBrief]:
    if not run_ids:
        return []
    rows = await db.execute(select(PeriodRun).where(PeriodRun.org_id == ctx.org_id, PeriodRun.id.in_(run_ids)))
    return [_brief(r) for r in rows.scalars()]


async def apply_payroll_allocation(db: AsyncSession, ctx: TenantContext, run_id: uuid.UUID, amount: Decimal) -> None:
    """Add an allocated direct-labour amount to the run (PAYROLL money-flow line) and recompute unit cost."""
    from app.modules.operations import service_money

    await service_money.apply_payroll_allocation(db, ctx, run_id, amount)


async def list_step_executions_by_month(db: AsyncSession, ctx: TenantContext, month: date) -> list[StepExecutionDTO]:
    """Steps executed during ``month`` (by executed_at, org-local calendar month in UTC)."""
    start = datetime.combine(month_start(month), time.min, tzinfo=UTC)
    end = datetime.combine(add_months(month_start(month), 1), time.min, tzinfo=UTC)
    rows = await db.execute(
        select(PeriodRunStep, PeriodRun.run_title)
        .join(PeriodRun, PeriodRun.id == PeriodRunStep.period_run_id)
        .where(
            PeriodRunStep.org_id == ctx.org_id,
            PeriodRunStep.executed_at >= start,
            PeriodRunStep.executed_at < end,
            PeriodRunStep.status.in_(("PASSED", "SKIPPED", "LOCKED")),
        )
        .order_by(PeriodRunStep.executed_at)
    )
    z = Decimal(0)
    return [StepExecutionDTO(s.period_run_id, title, s.id, s.step_name, s.node_shape, s.executed_by, s.executed_at,
                             s.input_qty or z, s.accepted_qty or z, s.rejected_qty or z, s.rework_qty or z)
            for s, title in rows.all()]  # fmt: skip


async def list_runs_for_costing(db: AsyncSession, ctx: TenantContext, date_from: date, date_to: date) -> list[RunBrief]:
    """Non-cancelled runs whose period month falls in [date_from, date_to] (batch costing comparison)."""
    rows = await db.execute(
        select(PeriodRun).where(PeriodRun.org_id == ctx.org_id, PeriodRun.status != "CANCELLED",
                                PeriodRun.period_month >= month_start(date_from), PeriodRun.period_month <= date_to)
        .order_by(PeriodRun.period_month, PeriodRun.run_title)
    )  # fmt: skip
    return [_brief(r) for r in rows.scalars()]


async def template_values(
    db: AsyncSession, ctx: TenantContext, *, run_id: uuid.UUID | None, step_id: uuid.UUID | None
) -> Any:
    """Report-template token values for a run/step: ``TemplateData(values, qc_rows, stock_item_id)``."""
    from app.modules.operations import render_data

    return await render_data.template_values(db, ctx, run_id=run_id, step_id=step_id)


async def step_run_ids(db: AsyncSession, ctx: TenantContext, step_ids: list[uuid.UUID]) -> dict[uuid.UUID, uuid.UUID]:
    """step id -> run id for steps of this org (link validation)."""
    if not step_ids:
        return {}
    rows = await db.execute(select(PeriodRunStep.id, PeriodRunStep.period_run_id).where(
        PeriodRunStep.org_id == ctx.org_id, PeriodRunStep.id.in_(step_ids)))  # fmt: skip
    return dict(rows.all())


async def install_platform_workflow_template(db: AsyncSession, ctx: TenantContext, key: str, payload: dict) -> bool:
    """Superadmin push: add the library template as a new DRAFT v1 (never touches published versions/runs)."""
    from app.modules.operations.models import WorkflowTemplate

    owner = await organization.get_org_brief(db, ctx.org_id)
    if owner is None:
        return False
    db.add(WorkflowTemplate(org_id=ctx.org_id, template_key=uuid.uuid4(), name=payload["name"],
                            description=payload.get("description"), iso_clause_ref=payload.get("iso_clause_ref"),
                            version=1, status="DRAFT", is_published=False,
                            graph_definition=payload["graph_definition"], created_by=ctx.user_id or owner.owner_user_id))  # fmt: skip
    await db.flush()
    return True


async def refresh_instrument_statuses(db: AsyncSession) -> int:
    """All orgs (platform session, no SET ROLE): persist VALID / DUE_SOON / EXPIRED. Returns rows changed."""
    today = datetime.now(UTC).date()
    res = await db.execute(update(CalibrationInstrument).where(CalibrationInstrument.status != _status_expr(today))
                           .values(status=_status_expr(today)))  # fmt: skip
    return int(res.rowcount or 0)


__all__ = [
    "RunBrief",
    "StepExecutionDTO",
    "apply_payroll_allocation",
    "get_runs_by_ids",
    "install_platform_workflow_template",
    "list_runs_for_costing",
    "list_step_executions_by_month",
    "refresh_calibration_statuses",
    "refresh_instrument_statuses",
    "resource_names",
    "seed_org_operations",
    "step_run_ids",
    "template_values",
]
