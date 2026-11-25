"""ISO compliance (NCR/CAPA, calibration, checklist, readiness, auditor invites), dashboard and the
stock-item facade."""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import write_audit
from app.core.context import TenantContext
from app.core.errors import InvalidStateError, NotFoundError, ValidationFailedError
from app.core.fy import add_months, format_month, month_start
from app.core.money import q2
from app.core.pagination import PageParams, paginate
from app.modules.accounts import interface as accounts
from app.modules.operations import service_runs as runs_svc
from app.modules.operations.common import (
    ITEM_KEY,
    ZERO,
    dz,
    get_instrument,
    get_ncr,
    item_names,
    now,
    run_scope,
    scoped_filter,
    today,
    user_names,
)
from app.modules.operations.interface import DUE_SOON_DAYS
from app.modules.operations.models import (
    CalibrationInstrument,
    IsoChecklistItem,
    IsoNcrCapaRecord,
    PeriodRun,
    PeriodRunStep,
)
from app.modules.operations.schemas import (
    AuditorInviteIn,
    CalibrateIn,
    ChecklistItemOut,
    ChecklistUpdateIn,
    ClauseScore,
    InstrumentIn,
    InstrumentOut,
    ItemStatsOut,
    KpiOut,
    NcrCloseIn,
    NcrIn,
    NcrOut,
    NcrUpdateIn,
    OpsDashboardOut,
    OpsItemOut,
    ReadinessOut,
)
from app.modules.organization import interface as organization
from app.modules.rbac import interface as rbac

NCR_EDIT_STATUSES = frozenset({"OPEN", "IN_PROGRESS", "UNDER_VERIFICATION"})
CHECKLIST_STATUSES = frozenset({"NOT_STARTED", "IN_PROGRESS", "COMPLIANT", "NOT_APPLICABLE"})
CLAUSE_TITLES = {"4": "Context of the organization", "5": "Leadership", "6": "Planning", "7": "Support",
                 "8": "Operation", "9": "Performance evaluation", "10": "Improvement"}  # fmt: skip


def instrument_status(next_due: date, on: date) -> str:
    if next_due < on:
        return "EXPIRED"
    if next_due <= on + timedelta(days=DUE_SOON_DAYS):
        return "DUE_SOON"
    return "VALID"


# ---------------------------------------------------------------- NCR
async def list_ncrs(
    db: AsyncSession, ctx: TenantContext, page: PageParams, status: str | None, run_id: uuid.UUID | None
) -> tuple[list[NcrOut], int]:
    stmt = select(IsoNcrCapaRecord).where(IsoNcrCapaRecord.org_id == ctx.org_id)
    if status:
        stmt = stmt.where(IsoNcrCapaRecord.status == status)
    if run_id:
        stmt = stmt.where(IsoNcrCapaRecord.period_run_id == run_id)
    scope = await run_scope(ctx, db)
    if scope.scoped_by_item:
        visible = select(PeriodRun.id).where(PeriodRun.org_id == ctx.org_id, scope.clause())
        stmt = stmt.where(IsoNcrCapaRecord.period_run_id.in_(visible))
    rows, total = await paginate(db, stmt.order_by(IsoNcrCapaRecord.created_at.desc()), page)
    return await runs_svc.ncr_outs(db, [r[0] for r in rows]), total


async def _ncr_out(db: AsyncSession, ncr: IsoNcrCapaRecord) -> NcrOut:
    await db.flush()
    return (await runs_svc.ncr_outs(db, [ncr]))[0]


async def _check_assignee(db: AsyncSession, ctx: TenantContext, user_id: uuid.UUID | None) -> None:
    if user_id and not await organization.is_member(db, ctx.org_id, user_id):
        raise ValidationFailedError("The assignee is not a member of this organization")


async def create_ncr(db: AsyncSession, ctx: TenantContext, body: NcrIn) -> NcrOut:
    if body.rejected_qty < 0:
        raise ValidationFailedError("Rejected quantity cannot be negative")
    if body.period_run_id:
        run = await db.get(PeriodRun, body.period_run_id)
        if run is None or run.org_id != ctx.org_id:
            raise NotFoundError("Run not found")
    if body.run_step_id:
        step = await db.get(PeriodRunStep, body.run_step_id)
        if (
            step is None
            or step.org_id != ctx.org_id
            or (body.period_run_id and step.period_run_id != body.period_run_id)
        ):
            raise NotFoundError("Step not found")
    await _check_assignee(db, ctx, body.assigned_to)
    ncr = await runs_svc.create_ncr(db, ctx, run_id=body.period_run_id, step_id=body.run_step_id,
                                    qty=body.rejected_qty, description=body.defect_description, source="MANUAL",
                                    assigned_to=body.assigned_to)  # fmt: skip
    return await _ncr_out(db, ncr)


async def get_ncr_out(db: AsyncSession, ctx: TenantContext, ncr_id: uuid.UUID) -> NcrOut:
    return await _ncr_out(db, await get_ncr(db, ctx, ncr_id))


async def update_ncr(db: AsyncSession, ctx: TenantContext, ncr_id: uuid.UUID, body: NcrUpdateIn) -> NcrOut:
    ncr = await get_ncr(db, ctx, ncr_id)
    if ncr.status == "CLOSED":
        raise InvalidStateError("Closed NCRs cannot be edited")
    before = ncr.to_dict()
    data = body.model_dump(exclude_unset=True)
    if "status" in data and data["status"] not in NCR_EDIT_STATUSES:
        raise ValidationFailedError("Status must be OPEN, IN_PROGRESS or UNDER_VERIFICATION (use close to close)")
    if "assigned_to" in data:
        await _check_assignee(db, ctx, data["assigned_to"])
    if data.get("defect_description") is not None and not data["defect_description"].strip():
        raise ValidationFailedError("Defect description cannot be empty")
    for k, v in data.items():
        if k == "defect_description" and v is None:
            continue
        setattr(ncr, k, v)
    await db.flush()
    await write_audit(db, ctx, "OPERATIONS", "UPDATE", "ncr", ncr.id, before=before, after=ncr.to_dict(),
                      changed_only=True)  # fmt: skip
    return await _ncr_out(db, ncr)


async def close_ncr(db: AsyncSession, ctx: TenantContext, ncr_id: uuid.UUID, body: NcrCloseIn) -> NcrOut:
    ncr = await get_ncr(db, ctx, ncr_id)
    if ncr.status == "CLOSED":
        raise InvalidStateError("This NCR is already closed")
    before = ncr.status
    ncr.status, ncr.verification_notes, ncr.closed_by, ncr.closed_at = (
        "CLOSED",
        body.verification_notes,
        ctx.user_id,
        now(),
    )
    await write_audit(db, ctx, "OPERATIONS", "TRANSITION", "ncr", ncr.id, before={"status": before},
                      after={"status": "CLOSED"}, reason=body.verification_notes)  # fmt: skip
    return await _ncr_out(db, ncr)


# ---------------------------------------------------------------- calibration
def instrument_out(i: CalibrationInstrument, on: date | None = None) -> InstrumentOut:
    on = on or today()
    return InstrumentOut(id=i.id, instrument_code=i.instrument_code, name=i.name, location=i.location,
                         range_spec=i.range_spec, least_count=i.least_count, last_calibrated_date=i.last_calibrated_date,
                         next_due_date=i.next_due_date, status=instrument_status(i.next_due_date, on),
                         days_to_due=(i.next_due_date - on).days, certificate_doc_id=i.certificate_doc_id)  # fmt: skip


async def list_instruments(db: AsyncSession, ctx: TenantContext, status: str | None) -> list[InstrumentOut]:
    rows = (await db.execute(select(CalibrationInstrument).where(CalibrationInstrument.org_id == ctx.org_id)
                             .order_by(CalibrationInstrument.next_due_date))).scalars()  # fmt: skip
    out = [instrument_out(i) for i in rows]
    return [o for o in out if o.status == status] if status else out


def _check_dates(last: date, nxt: date) -> None:
    if nxt <= last:
        raise ValidationFailedError("Next due date must be after the calibration date")


async def create_instrument(db: AsyncSession, ctx: TenantContext, body: InstrumentIn) -> InstrumentOut:
    _check_dates(body.last_calibrated_date, body.next_due_date)
    inst = CalibrationInstrument(org_id=ctx.org_id, **body.model_dump(),
                                 status=instrument_status(body.next_due_date, today()), created_at=now())  # fmt: skip
    db.add(inst)
    await db.flush()
    await write_audit(db, ctx, "OPERATIONS", "CREATE", "calibration_instrument", inst.id, after=inst.to_dict())
    return instrument_out(inst)


async def update_instrument(db: AsyncSession, ctx: TenantContext, iid: uuid.UUID, body: InstrumentIn) -> InstrumentOut:
    inst = await get_instrument(db, ctx, iid)
    _check_dates(body.last_calibrated_date, body.next_due_date)
    before = inst.to_dict()
    for k, v in body.model_dump().items():
        setattr(inst, k, v)
    inst.status = instrument_status(inst.next_due_date, today())
    await db.flush()
    await write_audit(db, ctx, "OPERATIONS", "UPDATE", "calibration_instrument", inst.id, before=before,
                      after=inst.to_dict(), changed_only=True)  # fmt: skip
    return instrument_out(inst)


async def calibrate_instrument(
    db: AsyncSession, ctx: TenantContext, iid: uuid.UUID, body: CalibrateIn
) -> InstrumentOut:
    inst = await get_instrument(db, ctx, iid)
    _check_dates(body.calibrated_on, body.next_due_date)
    if body.calibrated_on > today():
        raise ValidationFailedError("Calibration date cannot be in the future")
    before = inst.to_dict()
    inst.last_calibrated_date, inst.next_due_date = body.calibrated_on, body.next_due_date
    if body.certificate_doc_id:
        inst.certificate_doc_id = body.certificate_doc_id
    inst.status = instrument_status(inst.next_due_date, today())
    await db.flush()
    await write_audit(db, ctx, "OPERATIONS", "UPDATE", "calibration_instrument", inst.id, before=before,
                      after=inst.to_dict(), changed_only=True, reason="calibrated")  # fmt: skip
    return instrument_out(inst)


# ---------------------------------------------------------------- checklist & readiness
async def _checklist_outs(db: AsyncSession, items: list[IsoChecklistItem]) -> list[ChecklistItemOut]:
    names = await user_names(db, [i.updated_by for i in items])
    return [ChecklistItemOut(id=i.id, clause=i.clause, title=i.title, description=i.description, status=i.status,
                             evidence_document_ids=list(i.evidence_document_ids or []), notes=i.notes,
                             updated_by_name=names.get(i.updated_by) if i.updated_by else None,
                             updated_at=i.updated_at) for i in items]  # fmt: skip


async def _checklist(db: AsyncSession, ctx: TenantContext) -> list[IsoChecklistItem]:
    return list((await db.execute(select(IsoChecklistItem).where(IsoChecklistItem.org_id == ctx.org_id)
                                  .order_by(IsoChecklistItem.sort_order))).scalars())  # fmt: skip


async def list_checklist(db: AsyncSession, ctx: TenantContext) -> list[ChecklistItemOut]:
    return await _checklist_outs(db, await _checklist(db, ctx))


async def update_checklist(
    db: AsyncSession, ctx: TenantContext, item_id: uuid.UUID, body: ChecklistUpdateIn
) -> ChecklistItemOut:
    from app.modules.documents import interface as documents

    item = await db.get(IsoChecklistItem, item_id)
    if item is None or item.org_id != ctx.org_id:
        raise NotFoundError()
    before = item.to_dict()
    data = body.model_dump(exclude_unset=True)
    if "status" in data and data["status"] not in CHECKLIST_STATUSES:
        raise ValidationFailedError(f"Status must be one of {', '.join(sorted(CHECKLIST_STATUSES))}")
    if data.get("evidence_document_ids"):
        ids = list(dict.fromkeys(data["evidence_document_ids"]))
        if len(await documents.existing_document_ids(db, ctx, ids)) != len(ids):
            raise NotFoundError("Evidence document not found")
        data["evidence_document_ids"] = ids
    for k, v in data.items():
        if k in ("status", "evidence_document_ids") and v is None:
            continue
        setattr(item, k, v)
    item.updated_by, item.updated_at = ctx.user_id, now()
    await db.flush()
    await write_audit(db, ctx, "OPERATIONS", "UPDATE", "iso_checklist_item", item.id, before=before,
                      after=item.to_dict(), changed_only=True)  # fmt: skip
    return (await _checklist_outs(db, [item]))[0]


def _score(compliant: int, applicable: int) -> Decimal:
    return q2(Decimal(compliant) * 100 / applicable) if applicable else Decimal("100.00")


async def readiness(db: AsyncSession, ctx: TenantContext) -> ReadinessOut:
    groups: dict[str, list[IsoChecklistItem]] = defaultdict(list)
    for i in await _checklist(db, ctx):
        groups[i.clause.split(".")[0]].append(i)
    by_clause, comp_all, appl_all = [], 0, 0
    for clause in sorted(groups, key=lambda c: int(c) if c.isdigit() else 99):
        items = groups[clause]
        applicable = [i for i in items if i.status != "NOT_APPLICABLE"]
        comp = sum(1 for i in applicable if i.status == "COMPLIANT")
        comp_all, appl_all = comp_all + comp, appl_all + len(applicable)
        by_clause.append(ClauseScore(clause=clause, title=CLAUSE_TITLES.get(clause, f"Clause {clause}"),
                                     total=len(items), compliant=comp, score_pct=_score(comp, len(applicable))))  # fmt: skip
    open_ncrs = (await db.execute(select(func.count()).select_from(IsoNcrCapaRecord).where(
        IsoNcrCapaRecord.org_id == ctx.org_id, IsoNcrCapaRecord.status != "CLOSED"))).scalar_one()  # fmt: skip
    expired = (await db.execute(select(func.count()).select_from(CalibrationInstrument).where(
        CalibrationInstrument.org_id == ctx.org_id, CalibrationInstrument.next_due_date < today()))).scalar_one()  # fmt: skip
    score = _score(comp_all, appl_all) if groups else ZERO
    return ReadinessOut(
        score_pct=score, by_clause=by_clause, open_ncrs=int(open_ncrs), expired_instruments=int(expired)
    )


# ---------------------------------------------------------------- auditor invites
class _Grant(BaseModel):
    resource_type: str
    resource_id: uuid.UUID
    access_level: str


class _Invite(BaseModel):
    email: str
    role_id: uuid.UUID
    access_expires_at: Any
    acl_grants: list[_Grant]


async def invite_auditor(db: AsyncSession, ctx: TenantContext, body: AuditorInviteIn) -> Any:
    if body.access_expires_at <= now():
        raise ValidationFailedError("Access expiry must be in the future")
    role = await rbac.get_role_by_code(db, ctx.org_id, "AUDITOR")
    if role is None:
        raise NotFoundError("Auditor role not found")
    item_ids = list(dict.fromkeys(body.stock_item_ids or []))
    run_ids = list(dict.fromkeys(body.period_run_ids or []))
    if item_ids and len(await item_names(db, ctx, item_ids)) != len(item_ids):
        raise NotFoundError("Stock item not found")
    if run_ids:
        found = (await db.execute(select(PeriodRun.id).where(PeriodRun.org_id == ctx.org_id,
                                                             PeriodRun.id.in_(run_ids)))).scalars().all()  # fmt: skip
        if len(found) != len(run_ids):
            raise NotFoundError("Run not found")
    grants = [_Grant(resource_type="STOCK_ITEM", resource_id=i, access_level="READ") for i in item_ids]
    grants += [_Grant(resource_type="PERIOD_RUN", resource_id=i, access_level="READ") for i in run_ids]
    invite = _Invite(
        email=str(body.email), role_id=role.id, access_expires_at=body.access_expires_at, acl_grants=grants
    )
    out = await organization.invite_member(db, ctx, invite)  # type: ignore[arg-type]
    await write_audit(db, ctx, "OPERATIONS", "INVITE", "auditor_invitation", out.id,
                      after={"email": str(body.email), "stock_item_ids": item_ids, "period_run_ids": run_ids})  # fmt: skip
    return out


# ---------------------------------------------------------------- dashboard
async def dashboard(db: AsyncSession, ctx: TenantContext) -> OpsDashboardOut:
    scope = await run_scope(ctx, db)
    base = select(PeriodRun).where(PeriodRun.org_id == ctx.org_id, scope.clause())
    active = list((await db.execute(base.where(PeriodRun.status.in_(runs_svc.OPEN_RUN_STATES))
                                    .order_by(PeriodRun.created_at.desc()).limit(10))).scalars())  # fmt: skip
    active_count = (await db.execute(select(func.count()).select_from(
        base.where(PeriodRun.status.in_(runs_svc.OPEN_RUN_STATES)).subquery()))).scalar_one()  # fmt: skip
    ncrs = list((await db.execute(select(IsoNcrCapaRecord).where(
        IsoNcrCapaRecord.org_id == ctx.org_id, IsoNcrCapaRecord.status != "CLOSED")
        .order_by(IsoNcrCapaRecord.created_at.desc()).limit(10))).scalars())  # fmt: skip
    open_ncr_count = await readiness(db, ctx)
    instruments = [i for i in await list_instruments(db, ctx, None) if i.status != "VALID"]
    first = add_months(month_start(today()), -5)
    recent = list((await db.execute(base.where(PeriodRun.period_month >= first,
                                               PeriodRun.status != "CANCELLED"))).scalars())  # fmt: skip
    series = []
    for k in range(6):
        m = add_months(first, k)
        rs = [r for r in recent if r.period_month == m]
        planned = sum((r.planned_qty for r in rs), ZERO)
        acc, rej = sum((dz(r.accepted_qty) for r in rs), ZERO), sum((dz(r.rejected_qty) for r in rs), ZERO)
        series.append({"month": format_month(m), "planned_qty": str(planned), "accepted_qty": str(acc),
                       "rejected_qty": str(rej), "yield_pct": str(q2(acc * 100 / planned)) if planned else None})  # fmt: skip
    tot_acc = sum((dz(r.accepted_qty) for r in recent), ZERO)
    tot_rej = sum((dz(r.rejected_qty) for r in recent), ZERO)
    rej_rate = q2(tot_rej * 100 / (tot_acc + tot_rej)) if tot_acc + tot_rej else ZERO
    kpis = [KpiOut(key="active_runs", label="Active runs", value=Decimal(active_count), change_pct=None),
            KpiOut(key="open_ncrs", label="Open NCR/CAPA", value=Decimal(open_ncr_count.open_ncrs), change_pct=None),
            KpiOut(key="rejection_rate", label="Rejection rate % (6 months)", value=rej_rate, change_pct=None),
            KpiOut(key="calibration_due", label="Gauges due / expired", value=Decimal(len(instruments)),
                   change_pct=None)]  # fmt: skip
    return OpsDashboardOut(kpis=kpis, active_runs=await runs_svc.summaries(db, ctx, active),
                           open_ncrs=await runs_svc.ncr_outs(db, ncrs), calibration_due=instruments,
                           readiness_pct=open_ncr_count.score_pct, yield_series=series)  # fmt: skip


# ---------------------------------------------------------------- items facade (stock items via accounts)
# shortcut: stock-item CRUD/list is not in accounts.interface yet (requested in docs/plan/requests/S2.md);
# looked up by name so the facade works as soon as S2 exports it.
def _accounts_fn(name: str) -> Any:
    fn = getattr(accounts, name, None)
    if fn is None:
        raise NotImplementedError(f"accounts.{name} is awaited from stream S2 (see docs/plan/requests/S2.md)")
    return fn


async def _with_stats(db: AsyncSession, ctx: TenantContext, items: list[dict[str, Any]]) -> list[OpsItemOut]:
    stats = await runs_svc.item_stats(db, ctx, [uuid.UUID(str(i["id"])) for i in items])
    out = []
    for i in items:
        st = dict(stats.get(uuid.UUID(str(i["id"])), {}))
        wf = st.pop("workflow_count", 0)
        st = st or {"run_count": 0, "active_run_count": 0, "last_run_at": None, "avg_yield_pct": None,
                    "avg_unit_cost": None}  # fmt: skip
        out.append(OpsItemOut(**i, stats=ItemStatsOut(**st), workflow_count=wf))
    return out


async def list_items(
    db: AsyncSession, ctx: TenantContext, page: PageParams, q: str | None, target_type: str | None
) -> tuple[list[OpsItemOut], int]:
    acl = await scoped_filter(ctx, db, "STOCK_ITEM", ITEM_KEY)
    items, total = await _accounts_fn("list_stock_items_out")(db, ctx, q=q, target_type=target_type, acl=acl,
                                                              limit=page.limit, offset=page.offset)  # fmt: skip
    return await _with_stats(db, ctx, items), total


async def _assert_item(db: AsyncSession, ctx: TenantContext, item_id: uuid.UUID, level: str) -> None:
    from app.core.errors import PermissionDeniedError
    from app.core.permissions import at_least

    acl = await scoped_filter(ctx, db, "STOCK_ITEM", ITEM_KEY, "READ")
    if not acl.visible(item_id) or not await item_names(db, ctx, [item_id]):
        raise NotFoundError("Item not found")
    if level != "READ":
        wacl = await scoped_filter(ctx, db, "STOCK_ITEM", ITEM_KEY, level)
        if not wacl.visible(item_id) and not at_least(ctx.level(ITEM_KEY), level):
            raise PermissionDeniedError(details={"permission": ITEM_KEY, "required": level})


async def get_item(db: AsyncSession, ctx: TenantContext, item_id: uuid.UUID) -> OpsItemOut:
    await _assert_item(db, ctx, item_id, "READ")
    return (await _with_stats(db, ctx, [await _accounts_fn("get_stock_item_out")(db, ctx, item_id)]))[0]


async def create_item(db: AsyncSession, ctx: TenantContext, body: Any) -> OpsItemOut:
    item = await _accounts_fn("create_stock_item")(db, ctx, body)
    return (await _with_stats(db, ctx, [item]))[0]


async def update_item(db: AsyncSession, ctx: TenantContext, item_id: uuid.UUID, body: Any) -> OpsItemOut:
    await _assert_item(db, ctx, item_id, "WRITE")
    item = await _accounts_fn("update_stock_item")(db, ctx, item_id, body)
    return (await _with_stats(db, ctx, [item]))[0]


async def item_runs(db: AsyncSession, ctx: TenantContext, item_id: uuid.UUID) -> list[Any]:
    await _assert_item(db, ctx, item_id, "READ")
    return await runs_svc.runs_for_item(db, ctx, item_id)
