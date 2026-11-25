"""Token values for report templates (``documents`` renders ``{{run.*}}``, ``{{step.*}}``, ``{{ncr.*}}``,
``{{accounts.*}}`` through ``operations.interface.template_values``)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import TenantContext
from app.core.errors import NotFoundError
from app.core.money import to_str
from app.modules.operations import graph as g
from app.modules.operations.common import dz, user_names
from app.modules.operations.models import (
    CalibrationInstrument,
    IsoNcrCapaRecord,
    PeriodRun,
    PeriodRunStep,
    WorkflowTemplate,
)


@dataclass
class TemplateData:
    values: dict[str, str | None] = field(default_factory=dict)
    qc_rows: list[list[str]] | None = None
    stock_item_id: uuid.UUID | None = None


def _s(v: Any) -> str | None:
    if v is None:
        return None
    if hasattr(v, "quantize"):
        return to_str(v)
    if hasattr(v, "strftime"):
        return v.strftime("%Y-%m-%d %H:%M") if hasattr(v, "hour") else v.isoformat()
    return str(v)


def qc_rows(fields: list[dict[str, Any]], readings: dict[str, Any]) -> list[list[str]]:
    rows = []
    for f in fields:
        r = readings.get(f["key"]) or {}
        unit = f" {f['unit']}" if f.get("unit") else ""
        tol = f"-{f.get('tol_minus') or 0}/+{f.get('tol_plus') or 0}" if f.get("nominal") not in (None, "") else ""
        res = {True: "OK", False: "NOK"}.get(r.get("in_tolerance"), "-")
        if r.get("auto_filled"):
            res += " (auto)"
        rows.append([f.get("label") or f["key"], f"{f.get('nominal') or ''}{unit}".strip(), tol,
                     str(r.get("value") or ""), res])  # fmt: skip
    return rows


async def template_values(
    db: AsyncSession, ctx: TenantContext, *, run_id: uuid.UUID | None, step_id: uuid.UUID | None
) -> TemplateData:
    out = TemplateData()
    step = None
    if step_id:
        step = await db.get(PeriodRunStep, step_id)
        if step is None or step.org_id != ctx.org_id or (run_id and step.period_run_id != run_id):
            raise NotFoundError("Step not found")
        run_id = step.period_run_id
    if not run_id:
        return out
    run = await db.get(PeriodRun, run_id)
    if run is None or run.org_id != ctx.org_id:
        raise NotFoundError("Run not found")
    wf = await db.get(WorkflowTemplate, run.workflow_template_id)
    out.stock_item_id = run.stock_item_id
    net = dz(run.total_debit_cost) - dz(run.total_credit_recovery)
    yld = (dz(run.accepted_qty) * 100 / run.planned_qty) if run.planned_qty else None
    v = out.values
    v.update({"run.title": run.run_title, "run.period": run.period_month.strftime("%b %Y"), "run.status": run.status,
              "run.planned_qty": _s(run.planned_qty), "run.accepted_qty": _s(dz(run.accepted_qty)),
              "run.rejected_qty": _s(dz(run.rejected_qty)), "run.rework_qty": _s(dz(run.rework_qty)),
              "run.yield_pct": _s(yld), "run.workflow_name": wf.name if wf else None,
              "run.workflow_version": str(run.workflow_version), "run.started_at": _s(run.started_at),
              "run.completed_at": _s(run.completed_at), "accounts.total_cost": _s(net),
              "accounts.total_debit": _s(dz(run.total_debit_cost)),
              "accounts.total_credit": _s(dz(run.total_credit_recovery)),
              "accounts.unit_cost": _s(dz(run.computed_unit_cost))})  # fmt: skip
    ncr_q = select(IsoNcrCapaRecord).where(IsoNcrCapaRecord.period_run_id == run.id)
    if step is not None:
        names = await user_names(db, [step.executed_by, step.signed_off_by])
        inst = await db.get(CalibrationInstrument, step.instrument_id) if step.instrument_id else None
        v.update({"step.name": step.step_name, "step.status": step.status, "step.result": step.branch_taken,
                  "step.input_qty": _s(dz(step.input_qty)), "step.accepted_qty": _s(dz(step.accepted_qty)),
                  "step.rejected_qty": _s(dz(step.rejected_qty)), "step.rework_qty": _s(dz(step.rework_qty)),
                  "step.executed_by": names.get(step.executed_by) if step.executed_by else None,
                  "step.executed_at": _s(step.executed_at),
                  "step.signed_off_by": names.get(step.signed_off_by) if step.signed_off_by else None,
                  "step.instrument": f"{inst.instrument_code} {inst.name}" if inst else None,
                  "step.notes": step.notes or ""})  # fmt: skip
        readings = step.qc_measurements or {}
        for key, r in readings.items():
            v[f"step.qc.{key}"] = (r or {}).get("value")
        fields = g.config_of(g.node_map(run.graph_snapshot or {}).get(step.node_id, {})).get("qc_fields") or []
        out.qc_rows = qc_rows(fields, readings)
        ncr_q = ncr_q.where(IsoNcrCapaRecord.run_step_id == step.id)
    ncr = (await db.execute(ncr_q.order_by(IsoNcrCapaRecord.created_at.desc()).limit(1))).scalar()
    if ncr is not None:
        v.update({"ncr.number": ncr.ncr_number, "ncr.rejected_qty": _s(ncr.rejected_qty),
                  "ncr.defect_description": ncr.defect_description,
                  "ncr.root_cause_analysis": ncr.root_cause_analysis or "",
                  "ncr.corrective_action": ncr.corrective_action or "",
                  "ncr.preventive_action": ncr.preventive_action or "", "ncr.status": ncr.status})  # fmt: skip
    return out
