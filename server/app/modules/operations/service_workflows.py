"""Workflow templates: CRUD of drafts, validation, publish (immutable), versions, ISO library."""

from __future__ import annotations

import copy
import uuid
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import write_audit
from app.core.context import TenantContext
from app.core.errors import (
    InvalidStateError,
    NotFoundError,
    WorkflowInvalidError,
    WorkflowPublishedError,
)
from app.modules.operations import graph as g
from app.modules.operations.common import get_workflow, item_names, now, user_names
from app.modules.operations.models import PeriodRun, WorkflowTemplate
from app.modules.operations.schemas import (
    LibraryTemplateOut,
    ValidationIssue,
    WorkflowIn,
    WorkflowOut,
    WorkflowSummary,
    WorkflowUpdateIn,
    WorkflowValidationOut,
)
from app.modules.platform.interface import get_config, list_configs

ACTIVE_RUN_STATES = ("PLANNED", "IN_PROGRESS", "QC_HOLD")
EMPTY_GRAPH: dict[str, Any] = {"nodes": [], "edges": []}


def _graph_json(model: Any) -> dict[str, Any]:
    return model.model_dump(mode="json", exclude_none=False) if model is not None else copy.deepcopy(EMPTY_GRAPH)


async def _active_runs(db: AsyncSession, ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    if not ids:
        return {}
    rows = await db.execute(
        select(PeriodRun.workflow_template_id, func.count())
        .where(PeriodRun.workflow_template_id.in_(ids), PeriodRun.status.in_(ACTIVE_RUN_STATES))
        .group_by(PeriodRun.workflow_template_id)
    )
    return dict(rows.all())


async def _summaries(db: AsyncSession, ctx: TenantContext, wfs: list[WorkflowTemplate]) -> list[dict[str, Any]]:
    counts = await _active_runs(db, [w.id for w in wfs])
    names = await item_names(db, ctx, [w.stock_item_id for w in wfs])
    return [
        {"id": w.id, "template_key": w.template_key, "name": w.name, "description": w.description,
         "version": w.version, "status": w.status, "stock_item_id": w.stock_item_id,
         "stock_item_name": names.get(w.stock_item_id) if w.stock_item_id else None,
         "iso_clause_ref": w.iso_clause_ref, "node_count": len(g.nodes_of(w.graph_definition)),
         "active_run_count": counts.get(w.id, 0), "published_at": w.published_at, "created_at": w.created_at}
        for w in wfs
    ]  # fmt: skip


async def workflow_out(db: AsyncSession, ctx: TenantContext, wf: WorkflowTemplate) -> WorkflowOut:
    await db.refresh(wf)
    base = (await _summaries(db, ctx, [wf]))[0]
    names = await user_names(db, [wf.created_by])
    return WorkflowOut(**base, graph_definition=wf.graph_definition, created_by_name=names.get(wf.created_by, ""))


def _issues(items: list[g.Issue]) -> list[ValidationIssue]:
    return [ValidationIssue(node_id=i.node_id, edge_id=i.edge_id, message=i.message) for i in items]


def validation_out(graph: dict[str, Any]) -> WorkflowValidationOut:
    res = g.validate_graph(graph)
    return WorkflowValidationOut(valid=res.valid, errors=_issues(res.errors), warnings=_issues(res.warnings))


async def _check_item(db: AsyncSession, ctx: TenantContext, item_id: uuid.UUID | None) -> None:
    if item_id and not await item_names(db, ctx, [item_id]):
        raise NotFoundError("Stock item not found")


async def list_library(db: AsyncSession) -> list[LibraryTemplateOut]:
    return [LibraryTemplateOut(key=k, name=p["name"], description=p.get("description") or "",
                               iso_clause_ref=p.get("iso_clause_ref"), graph_definition=p["graph_definition"])
            for k, p in await list_configs(db, "ISO_WORKFLOW_TEMPLATES")]  # fmt: skip


async def list_workflows(
    db: AsyncSession, ctx: TenantContext, q: str | None, stock_item_id: uuid.UUID | None, all_versions: bool
) -> list[WorkflowSummary]:
    stmt = select(WorkflowTemplate).where(WorkflowTemplate.org_id == ctx.org_id)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(WorkflowTemplate.name.ilike(like), WorkflowTemplate.description.ilike(like)))
    if stock_item_id:
        stmt = stmt.where(WorkflowTemplate.stock_item_id == stock_item_id)
    wfs = list((await db.execute(stmt.order_by(WorkflowTemplate.name, WorkflowTemplate.version.desc()))).scalars())
    if not all_versions:
        latest: dict[uuid.UUID, WorkflowTemplate] = {}
        for w in wfs:
            latest.setdefault(w.template_key, w)
        wfs = list(latest.values())
    return [WorkflowSummary(**s) for s in await _summaries(db, ctx, wfs)]


async def create_workflow(db: AsyncSession, ctx: TenantContext, body: WorkflowIn) -> WorkflowOut:
    graph = _graph_json(body.graph_definition)
    description, clause = body.description, body.iso_clause_ref
    if body.from_library_key:
        try:
            tpl = await get_config(db, "ISO_WORKFLOW_TEMPLATES", body.from_library_key)
        except NotFoundError:
            raise NotFoundError("Library template not found") from None
        graph = copy.deepcopy(tpl["graph_definition"])
        description = description if description is not None else tpl.get("description")
        clause = clause if clause is not None else tpl.get("iso_clause_ref")
    await _check_item(db, ctx, body.stock_item_id)
    wf = WorkflowTemplate(org_id=ctx.org_id, template_key=uuid.uuid4(), name=body.name, description=description,
                          stock_item_id=body.stock_item_id, iso_clause_ref=clause, version=1, status="DRAFT",
                          is_published=False, graph_definition=graph, created_by=ctx.user_id)  # fmt: skip
    db.add(wf)
    await db.flush()
    await write_audit(db, ctx, "OPERATIONS", "CREATE", "workflow_template", wf.id, after=wf.to_dict())
    return await workflow_out(db, ctx, wf)


async def get_workflow_out(db: AsyncSession, ctx: TenantContext, wid: uuid.UUID) -> WorkflowOut:
    return await workflow_out(db, ctx, await get_workflow(db, ctx, wid))


def _assert_draft(wf: WorkflowTemplate) -> None:
    if wf.status != "DRAFT":
        raise WorkflowPublishedError("Published workflows are immutable; create a new version")


async def update_workflow(db: AsyncSession, ctx: TenantContext, wid: uuid.UUID, body: WorkflowUpdateIn) -> WorkflowOut:
    wf = await get_workflow(db, ctx, wid)
    _assert_draft(wf)
    before = wf.to_dict()
    fields = body.model_fields_set
    if "name" in fields and body.name:
        wf.name = body.name
    if "description" in fields:
        wf.description = body.description
    if "iso_clause_ref" in fields:
        wf.iso_clause_ref = body.iso_clause_ref
    if "stock_item_id" in fields:
        await _check_item(db, ctx, body.stock_item_id)
        wf.stock_item_id = body.stock_item_id
    if "graph_definition" in fields and body.graph_definition is not None:
        wf.graph_definition = _graph_json(body.graph_definition)
    wf.updated_at = now()
    await db.flush()
    await write_audit(db, ctx, "OPERATIONS", "UPDATE", "workflow_template", wf.id, before=before,
                      after=wf.to_dict(), changed_only=True)  # fmt: skip
    return await workflow_out(db, ctx, wf)


async def delete_workflow(db: AsyncSession, ctx: TenantContext, wid: uuid.UUID) -> None:
    wf = await get_workflow(db, ctx, wid)
    _assert_draft(wf)
    used = (await db.execute(select(PeriodRun.id).where(PeriodRun.workflow_template_id == wf.id).limit(1))).first()
    if used:
        raise InvalidStateError("This workflow version is used by runs")
    before = wf.to_dict()
    await db.delete(wf)
    await db.flush()
    await write_audit(db, ctx, "OPERATIONS", "DELETE", "workflow_template", wid, before=before)


async def validate_workflow(db: AsyncSession, ctx: TenantContext, wid: uuid.UUID) -> WorkflowValidationOut:
    return validation_out((await get_workflow(db, ctx, wid)).graph_definition)


async def publish_workflow(db: AsyncSession, ctx: TenantContext, wid: uuid.UUID) -> WorkflowOut:
    wf = await get_workflow(db, ctx, wid)
    _assert_draft(wf)
    res = validation_out(wf.graph_definition)
    if not res.valid:
        raise WorkflowInvalidError(details={"errors": [i.model_dump() for i in res.errors]})
    wf.status, wf.is_published, wf.published_at, wf.updated_at = "PUBLISHED", True, now(), now()
    await db.flush()
    await write_audit(db, ctx, "OPERATIONS", "APPROVE", "workflow_template", wf.id,
                      after={"status": "PUBLISHED", "version": wf.version})  # fmt: skip
    return await workflow_out(db, ctx, wf)


async def new_version(db: AsyncSession, ctx: TenantContext, wid: uuid.UUID) -> WorkflowOut:
    src = await get_workflow(db, ctx, wid)
    family = list((await db.execute(select(WorkflowTemplate).where(
        WorkflowTemplate.org_id == ctx.org_id, WorkflowTemplate.template_key == src.template_key))).scalars())  # fmt: skip
    if any(w.status == "DRAFT" for w in family):
        raise InvalidStateError("A draft version already exists for this workflow")
    wf = WorkflowTemplate(org_id=ctx.org_id, template_key=src.template_key, name=src.name,
                          description=src.description, stock_item_id=src.stock_item_id,
                          iso_clause_ref=src.iso_clause_ref, version=max(w.version for w in family) + 1,
                          status="DRAFT", is_published=False, graph_definition=copy.deepcopy(src.graph_definition),
                          created_by=ctx.user_id)  # fmt: skip
    db.add(wf)
    await db.flush()
    await write_audit(db, ctx, "OPERATIONS", "CREATE", "workflow_template", wf.id,
                      after={"version": wf.version, "copied_from": str(src.id)})  # fmt: skip
    return await workflow_out(db, ctx, wf)


async def list_versions(db: AsyncSession, ctx: TenantContext, wid: uuid.UUID) -> list[WorkflowSummary]:
    src = await get_workflow(db, ctx, wid)
    wfs = list((await db.execute(select(WorkflowTemplate).where(
        WorkflowTemplate.org_id == ctx.org_id, WorkflowTemplate.template_key == src.template_key
    ).order_by(WorkflowTemplate.version.desc()))).scalars())  # fmt: skip
    return [WorkflowSummary(**s) for s in await _summaries(db, ctx, wfs)]
