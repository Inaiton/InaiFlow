"""Shared helpers for operations services: loaders, record-level ACL scoping, name lookups."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import ColumnElement, false, or_, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import TenantContext
from app.core.deps import AclFilter, acl_list_filter, acl_overrides
from app.core.errors import NotFoundError, PermissionDeniedError
from app.core.permissions import at_least
from app.modules.accounts import interface as accounts
from app.modules.identity import interface as identity
from app.modules.operations.models import (
    CalibrationInstrument,
    IsoNcrCapaRecord,
    PeriodRun,
    PeriodRunStep,
    WorkflowTemplate,
)

RUN_KEY = "operations.runs_execution"
ITEM_KEY = "operations.items"
ZERO = Decimal(0)


def now() -> datetime:
    return datetime.now(UTC)


def today() -> date:
    return now().date()


def dz(v: Decimal | None) -> Decimal:
    return v if v is not None else ZERO


async def user_names(db: AsyncSession, ids: list[uuid.UUID | None]) -> dict[uuid.UUID, str]:
    briefs = await identity.user_briefs(db, [i for i in ids if i])
    return {k: v.full_name for k, v in briefs.items()}


async def item_names(db: AsyncSession, ctx: TenantContext, ids: list[uuid.UUID | None]) -> dict[uuid.UUID, str]:
    clean = list({i for i in ids if i})
    return await accounts.resource_names(db, ctx, "STOCK_ITEM", clean) if clean else {}


# ---------------------------------------------------------------- record-level ACL
async def scoped_filter(
    ctx: TenantContext, db: AsyncSession, resource_type: str, module_key: str, level: str = "READ"
) -> AclFilter:
    """``acl_list_filter`` + scoping rule: an external collaborator who holds record grants of a type sees
    ONLY the granted records of that type (the grant scopes, it does not merely add)."""
    f = await acl_list_filter(ctx, db, resource_type, module_key, level)
    if ctx.is_external and not ctx.is_owner and f.allowed:
        return AclFilter("NONE", f.allowed, f.denied, level)
    return f


class RunScope:
    """Visibility of runs: PERIOD_RUN grants, plus (for scoped externals) runs of granted STOCK_ITEMs."""

    def __init__(self, runs: AclFilter, items: AclFilter, scoped_by_item: bool) -> None:
        self.runs, self.items, self.scoped_by_item = runs, items, scoped_by_item

    def clause(self) -> ColumnElement[bool]:
        if self.scoped_by_item:
            conds = []
            if self.runs.allowed:
                conds.append(PeriodRun.id.in_(self.runs.allowed))
            if self.items.allowed:
                conds.append(PeriodRun.stock_item_id.in_(self.items.allowed))
            return or_(*conds) if conds else false()
        return self.runs.clause(PeriodRun.id)

    def visible(self, run: PeriodRun) -> bool:
        if self.scoped_by_item:
            return run.id in self.runs.allowed or (
                run.stock_item_id is not None and run.stock_item_id in self.items.allowed
            )
        return self.runs.visible(run.id)


async def run_scope(ctx: TenantContext, db: AsyncSession, level: str = "READ") -> RunScope:
    runs = await scoped_filter(ctx, db, "PERIOD_RUN", RUN_KEY, level)
    items = await scoped_filter(ctx, db, "STOCK_ITEM", ITEM_KEY, level)
    scoped = ctx.is_external and not ctx.is_owner and bool(runs.allowed or items.allowed)
    return RunScope(runs, items, scoped)


async def run_level(ctx: TenantContext, db: AsyncSession, run: PeriodRun) -> str:
    if ctx.is_owner:
        return "FULL"
    over = await acl_overrides(ctx, db, "PERIOD_RUN", [run.id])
    if run.id in over:
        return over[run.id]
    scope = await run_scope(ctx, db, "READ")
    if scope.scoped_by_item:
        if run.stock_item_id and run.stock_item_id in scope.items.allowed:
            item_over = await acl_overrides(ctx, db, "STOCK_ITEM", [run.stock_item_id])
            return item_over.get(run.stock_item_id, "READ")
        return "NONE"
    return ctx.level(RUN_KEY)


async def assert_run_access(ctx: TenantContext, db: AsyncSession, run: PeriodRun, level: str) -> None:
    eff = await run_level(ctx, db, run)
    if eff == "NONE":
        raise NotFoundError()
    if not at_least(eff, level):
        raise PermissionDeniedError(details={"permission": RUN_KEY, "required": level, "resource": "PERIOD_RUN"})


# ---------------------------------------------------------------- loaders
async def get_workflow(db: AsyncSession, ctx: TenantContext, wid: uuid.UUID) -> WorkflowTemplate:
    wf = await db.get(WorkflowTemplate, wid)
    if wf is None or wf.org_id != ctx.org_id:
        raise NotFoundError("Workflow not found")
    return wf


async def get_run(db: AsyncSession, ctx: TenantContext, run_id: uuid.UUID, *, lock: bool = False) -> PeriodRun:
    stmt = select(PeriodRun).where(PeriodRun.id == run_id, PeriodRun.org_id == ctx.org_id)
    if lock:
        stmt = stmt.with_for_update()
    run = (await db.execute(stmt)).scalar_one_or_none()
    if run is None:
        raise NotFoundError("Run not found")
    return run


async def get_steps(db: AsyncSession, run_id: uuid.UUID, *, lock: bool = False) -> list[PeriodRunStep]:
    stmt = select(PeriodRunStep).where(PeriodRunStep.period_run_id == run_id).order_by(PeriodRunStep.sequence)
    if lock:
        stmt = stmt.with_for_update()
    return list((await db.execute(stmt)).scalars())


async def get_ncr(db: AsyncSession, ctx: TenantContext, ncr_id: uuid.UUID) -> IsoNcrCapaRecord:
    ncr = await db.get(IsoNcrCapaRecord, ncr_id)
    if ncr is None or ncr.org_id != ctx.org_id:
        raise NotFoundError("NCR not found")
    return ncr


async def get_instrument(db: AsyncSession, ctx: TenantContext, iid: uuid.UUID) -> CalibrationInstrument:
    inst = await db.get(CalibrationInstrument, iid)
    if inst is None or inst.org_id != ctx.org_id:
        raise NotFoundError("Instrument not found")
    return inst


def always() -> ColumnElement[bool]:
    return true()


def snapshot(obj: Any) -> dict[str, Any]:
    return obj.to_dict()
