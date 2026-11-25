"""Operations routes (contract section ``operations``). Thin handlers: parse, guard, call one service fn."""

from __future__ import annotations

import uuid
from typing import Annotated, Any
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query, Response, status

from app.core.context import TenantContext
from app.core.deps import TenantDB, require
from app.core.idempotency import Idem
from app.core.pagination import Page, Paging
from app.modules.operations import dossier
from app.modules.operations import service_iso as iso
from app.modules.operations import service_money as money
from app.modules.operations import service_runs as runs
from app.modules.operations import service_workflows as wfs
from app.modules.operations.schemas import (
    AuditorInviteIn,
    CalibrateIn,
    ChecklistItemOut,
    ChecklistUpdateIn,
    InstrumentIn,
    InstrumentOut,
    InvitationOut,
    LibraryTemplateOut,
    LinkVoucherIn,
    MoneyFlowOut,
    NcrCloseIn,
    NcrIn,
    NcrOut,
    NcrUpdateIn,
    OpsDashboardOut,
    OpsItemOut,
    OptionalReasonIn,
    ReadinessOut,
    ReasonIn,
    RunCreateIn,
    RunOut,
    RunPostingIn,
    RunPostingOut,
    RunStatus,
    RunSummary,
    StepExecuteIn,
    StepExecuteOut,
    StepOut,
    StockItemIn,
    WorkflowIn,
    WorkflowOut,
    WorkflowSummary,
    WorkflowUpdateIn,
    WorkflowValidationOut,
)

router = APIRouter(tags=["operations"])
NO_CONTENT = status.HTTP_204_NO_CONTENT
CREATED = status.HTTP_201_CREATED


def _g(key: str, level: str, acl: str | None = None) -> Any:
    return Annotated[TenantContext, Depends(require(f"operations.{key}", level, acl_resource=acl))]


DashRead = _g("dashboard", "READ", "PERIOD_RUN")
ItemsRead = _g("items", "READ", "STOCK_ITEM")
ItemsWrite = _g("items", "WRITE", "STOCK_ITEM")
WfRead, WfWrite, WfFull = _g("workflows", "READ"), _g("workflows", "WRITE"), _g("workflows", "FULL")
RunRead = _g("runs_execution", "READ", "PERIOD_RUN")
RunWrite = _g("runs_execution", "WRITE", "PERIOD_RUN")
RunFull = _g("runs_execution", "FULL", "PERIOD_RUN")
AccRead = _g("runs_accounting", "READ", "PERIOD_RUN")
AccWrite = _g("runs_accounting", "WRITE", "PERIOD_RUN")
QcWrite, QcFull = _g("qc_signoff", "WRITE", "PERIOD_RUN"), _g("qc_signoff", "FULL", "PERIOD_RUN")
IsoRead, IsoWrite, IsoFull = _g("iso_compliance", "READ"), _g("iso_compliance", "WRITE"), _g("iso_compliance", "FULL")


# ---------------------------------------------------------------- dashboard & items
@router.get("/operations/dashboard", response_model=OpsDashboardOut)
async def dashboard(ctx: DashRead, db: TenantDB) -> OpsDashboardOut:
    return await iso.dashboard(db, ctx)


@router.get("/operations/items", response_model=Page[OpsItemOut])
async def list_items(ctx: ItemsRead, db: TenantDB, page: Paging, q: str | None = None,
                     target_type: str | None = None) -> Page[OpsItemOut]:  # fmt: skip
    items, total = await iso.list_items(db, ctx, page, q, target_type)
    return Page(items=items, total=total, limit=page.limit, offset=page.offset)


@router.post("/operations/items", response_model=OpsItemOut, status_code=CREATED)
async def create_item(body: StockItemIn, ctx: ItemsWrite, db: TenantDB) -> OpsItemOut:
    return await iso.create_item(db, ctx, body)


@router.get("/operations/items/{item_id}", response_model=OpsItemOut)
async def get_item(item_id: uuid.UUID, ctx: ItemsRead, db: TenantDB) -> OpsItemOut:
    return await iso.get_item(db, ctx, item_id)


@router.patch("/operations/items/{item_id}", response_model=OpsItemOut)
async def update_item(item_id: uuid.UUID, body: StockItemIn, ctx: ItemsWrite, db: TenantDB) -> OpsItemOut:
    return await iso.update_item(db, ctx, item_id, body)


@router.get("/operations/items/{item_id}/runs", response_model=list[RunSummary])
async def item_runs(item_id: uuid.UUID, ctx: ItemsRead, db: TenantDB) -> list[RunSummary]:
    return await iso.item_runs(db, ctx, item_id)


# ---------------------------------------------------------------- workflows
@router.get("/operations/workflow-library", response_model=list[LibraryTemplateOut])
async def workflow_library(ctx: WfRead, db: TenantDB) -> list[LibraryTemplateOut]:
    return await wfs.list_library(db)


@router.get("/operations/workflows", response_model=list[WorkflowSummary])
async def list_workflows(ctx: WfRead, db: TenantDB, q: str | None = None, stock_item_id: uuid.UUID | None = None,
                         all_versions: bool = False) -> list[WorkflowSummary]:  # fmt: skip
    return await wfs.list_workflows(db, ctx, q, stock_item_id, all_versions)


@router.post("/operations/workflows", response_model=WorkflowOut, status_code=CREATED)
async def create_workflow(body: WorkflowIn, ctx: WfWrite, db: TenantDB) -> WorkflowOut:
    return await wfs.create_workflow(db, ctx, body)


@router.get("/operations/workflows/{workflow_id}", response_model=WorkflowOut)
async def get_workflow(workflow_id: uuid.UUID, ctx: WfRead, db: TenantDB) -> WorkflowOut:
    return await wfs.get_workflow_out(db, ctx, workflow_id)


@router.put("/operations/workflows/{workflow_id}", response_model=WorkflowOut)
async def update_workflow(workflow_id: uuid.UUID, body: WorkflowUpdateIn, ctx: WfWrite, db: TenantDB) -> WorkflowOut:
    return await wfs.update_workflow(db, ctx, workflow_id, body)


@router.delete("/operations/workflows/{workflow_id}", status_code=NO_CONTENT)
async def delete_workflow(workflow_id: uuid.UUID, ctx: WfFull, db: TenantDB) -> Response:
    await wfs.delete_workflow(db, ctx, workflow_id)
    return Response(status_code=NO_CONTENT)


@router.post("/operations/workflows/{workflow_id}/validate", response_model=WorkflowValidationOut)
async def validate_workflow(workflow_id: uuid.UUID, ctx: WfRead, db: TenantDB) -> WorkflowValidationOut:
    return await wfs.validate_workflow(db, ctx, workflow_id)


@router.post("/operations/workflows/{workflow_id}/publish", response_model=WorkflowOut)
async def publish_workflow(workflow_id: uuid.UUID, ctx: WfFull, db: TenantDB) -> WorkflowOut:
    return await wfs.publish_workflow(db, ctx, workflow_id)


@router.post("/operations/workflows/{workflow_id}/new-version", response_model=WorkflowOut, status_code=CREATED)
async def new_version(workflow_id: uuid.UUID, ctx: WfWrite, db: TenantDB) -> WorkflowOut:
    return await wfs.new_version(db, ctx, workflow_id)


@router.get("/operations/workflows/{workflow_id}/versions", response_model=list[WorkflowSummary])
async def list_versions(workflow_id: uuid.UUID, ctx: WfRead, db: TenantDB) -> list[WorkflowSummary]:
    return await wfs.list_versions(db, ctx, workflow_id)


# ---------------------------------------------------------------- runs
@router.get("/operations/runs", response_model=Page[RunSummary])
async def list_runs(ctx: RunRead, db: TenantDB, page: Paging, status: RunStatus | None = None,
                    stock_item_id: uuid.UUID | None = None, period_month: str | None = None,
                    q: str | None = None) -> Page[RunSummary]:  # fmt: skip
    items, total = await runs.list_runs(db, ctx, page, status=status, stock_item_id=stock_item_id,
                                        period_month=period_month, q=q)  # fmt: skip
    return Page(items=items, total=total, limit=page.limit, offset=page.offset)


@router.post("/operations/runs", response_model=RunOut, status_code=CREATED)
async def create_run(body: RunCreateIn, ctx: RunWrite, db: TenantDB, idem: Idem) -> RunOut:
    return await idem.save(await runs.create_run(db, ctx, body), 201)


@router.get("/operations/runs/{run_id}", response_model=RunOut)
async def get_run(run_id: uuid.UUID, ctx: RunRead, db: TenantDB) -> RunOut:
    return await runs.get_run_out(db, ctx, run_id)


@router.post("/operations/runs/{run_id}/start", response_model=RunOut)
async def start_run(run_id: uuid.UUID, ctx: RunWrite, db: TenantDB) -> RunOut:
    return await runs.start_run(db, ctx, run_id)


@router.post("/operations/runs/{run_id}/hold", response_model=RunOut)
async def hold_run(run_id: uuid.UUID, body: ReasonIn, ctx: RunWrite, db: TenantDB) -> RunOut:
    return await runs.hold_run(db, ctx, run_id, body)


@router.post("/operations/runs/{run_id}/resume", response_model=RunOut)
async def resume_run(run_id: uuid.UUID, ctx: RunWrite, db: TenantDB) -> RunOut:
    return await runs.resume_run(db, ctx, run_id)


@router.post("/operations/runs/{run_id}/cancel", response_model=RunOut)
async def cancel_run(run_id: uuid.UUID, body: ReasonIn, ctx: RunFull, db: TenantDB) -> RunOut:
    return await runs.cancel_run(db, ctx, run_id, body)


@router.post("/operations/runs/{run_id}/complete", response_model=RunOut)
async def complete_run(run_id: uuid.UUID, ctx: RunFull, db: TenantDB) -> RunOut:
    return await runs.complete_run(db, ctx, run_id)


@router.post("/operations/runs/{run_id}/steps/{step_id}/execute", response_model=StepExecuteOut)
async def execute_step(run_id: uuid.UUID, step_id: uuid.UUID, body: StepExecuteIn, ctx: RunWrite, db: TenantDB,
                       idem: Idem) -> StepExecuteOut:  # fmt: skip
    return await idem.save(await runs.execute_step(db, ctx, run_id, step_id, body))


@router.post("/operations/runs/{run_id}/steps/{step_id}/skip", response_model=StepExecuteOut)
async def skip_step(run_id: uuid.UUID, step_id: uuid.UUID, body: ReasonIn, ctx: RunWrite, db: TenantDB,
                    idem: Idem) -> StepExecuteOut:  # fmt: skip
    return await idem.save(await runs.skip_step(db, ctx, run_id, step_id, body))


@router.post("/operations/runs/{run_id}/steps/{step_id}/succeed", response_model=StepExecuteOut)
async def succeed_step(run_id: uuid.UUID, step_id: uuid.UUID, body: OptionalReasonIn, ctx: RunWrite,
                       db: TenantDB, idem: Idem) -> StepExecuteOut:  # fmt: skip
    return await idem.save(await runs.succeed_step(db, ctx, run_id, step_id, body))


@router.post("/operations/runs/{run_id}/steps/{step_id}/signoff", response_model=StepOut)
async def signoff_step(run_id: uuid.UUID, step_id: uuid.UUID, ctx: QcWrite, db: TenantDB) -> StepOut:
    return await runs.signoff_step(db, ctx, run_id, step_id)


@router.post("/operations/runs/{run_id}/steps/{step_id}/reopen", response_model=StepOut)
async def reopen_step(run_id: uuid.UUID, step_id: uuid.UUID, body: ReasonIn, ctx: QcFull, db: TenantDB) -> StepOut:
    return await runs.reopen_step(db, ctx, run_id, step_id, body)


@router.get("/operations/runs/{run_id}/money-flow", response_model=MoneyFlowOut)
async def money_flow(run_id: uuid.UUID, ctx: AccRead, db: TenantDB) -> MoneyFlowOut:
    return await money.get_money_flow(db, ctx, run_id)


@router.post("/operations/runs/{run_id}/postings", response_model=RunPostingOut, status_code=CREATED)
async def post_to_run(run_id: uuid.UUID, body: RunPostingIn, ctx: AccWrite, db: TenantDB, idem: Idem) -> RunPostingOut:
    return await idem.save(await money.post_to_run(db, ctx, run_id, body), 201)


@router.post("/operations/runs/{run_id}/linked-vouchers", response_model=MoneyFlowOut)
async def link_voucher(run_id: uuid.UUID, body: LinkVoucherIn, ctx: AccWrite, db: TenantDB) -> MoneyFlowOut:
    return await money.link_voucher(db, ctx, run_id, body)


@router.delete("/operations/runs/{run_id}/linked-vouchers/{voucher_id}", status_code=NO_CONTENT)
async def unlink_voucher(run_id: uuid.UUID, voucher_id: uuid.UUID, ctx: AccWrite, db: TenantDB) -> Response:
    await money.unlink_voucher(db, ctx, run_id, voucher_id)
    return Response(status_code=NO_CONTENT)


@router.get("/operations/runs/{run_id}/dossier", response_class=Response,
            responses={200: {"content": {"application/pdf": {}, "application/vnd.openxmlformats-officedocument."
                                                             "wordprocessingml.document": {}}}})  # fmt: skip
async def run_dossier(run_id: uuid.UUID, ctx: RunRead, db: TenantDB, format: str = Query(),  # noqa: A002
                      save: bool = False) -> Response:  # fmt: skip
    data, mime, name = await dossier.export_dossier(db, ctx, run_id, format, save)
    return Response(content=data, media_type=mime,
                    headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}"})  # fmt: skip


# ---------------------------------------------------------------- ISO compliance
@router.get("/operations/ncr", response_model=Page[NcrOut])
async def list_ncrs(ctx: IsoRead, db: TenantDB, page: Paging, status: str | None = None,
                    period_run_id: uuid.UUID | None = None) -> Page[NcrOut]:  # fmt: skip
    items, total = await iso.list_ncrs(db, ctx, page, status, period_run_id)
    return Page(items=items, total=total, limit=page.limit, offset=page.offset)


@router.post("/operations/ncr", response_model=NcrOut, status_code=CREATED)
async def create_ncr(body: NcrIn, ctx: IsoWrite, db: TenantDB) -> NcrOut:
    return await iso.create_ncr(db, ctx, body)


@router.get("/operations/ncr/{ncr_id}", response_model=NcrOut)
async def get_ncr(ncr_id: uuid.UUID, ctx: IsoRead, db: TenantDB) -> NcrOut:
    return await iso.get_ncr_out(db, ctx, ncr_id)


@router.patch("/operations/ncr/{ncr_id}", response_model=NcrOut)
async def update_ncr(ncr_id: uuid.UUID, body: NcrUpdateIn, ctx: IsoWrite, db: TenantDB) -> NcrOut:
    return await iso.update_ncr(db, ctx, ncr_id, body)


@router.post("/operations/ncr/{ncr_id}/close", response_model=NcrOut)
async def close_ncr(ncr_id: uuid.UUID, body: NcrCloseIn, ctx: IsoFull, db: TenantDB) -> NcrOut:
    return await iso.close_ncr(db, ctx, ncr_id, body)


@router.get("/operations/instruments", response_model=list[InstrumentOut])
async def list_instruments(ctx: IsoRead, db: TenantDB, status: str | None = None) -> list[InstrumentOut]:
    return await iso.list_instruments(db, ctx, status)


@router.post("/operations/instruments", response_model=InstrumentOut, status_code=CREATED)
async def create_instrument(body: InstrumentIn, ctx: IsoWrite, db: TenantDB) -> InstrumentOut:
    return await iso.create_instrument(db, ctx, body)


@router.patch("/operations/instruments/{instrument_id}", response_model=InstrumentOut)
async def update_instrument(instrument_id: uuid.UUID, body: InstrumentIn, ctx: IsoWrite, db: TenantDB) -> InstrumentOut:
    return await iso.update_instrument(db, ctx, instrument_id, body)


@router.post("/operations/instruments/{instrument_id}/calibrate", response_model=InstrumentOut)
async def calibrate(instrument_id: uuid.UUID, body: CalibrateIn, ctx: IsoWrite, db: TenantDB) -> InstrumentOut:
    return await iso.calibrate_instrument(db, ctx, instrument_id, body)


@router.get("/operations/iso/checklist", response_model=list[ChecklistItemOut])
async def checklist(ctx: IsoRead, db: TenantDB) -> list[ChecklistItemOut]:
    return await iso.list_checklist(db, ctx)


@router.patch("/operations/iso/checklist/{item_id}", response_model=ChecklistItemOut)
async def update_checklist(
    item_id: uuid.UUID, body: ChecklistUpdateIn, ctx: IsoWrite, db: TenantDB
) -> ChecklistItemOut:
    return await iso.update_checklist(db, ctx, item_id, body)


@router.get("/operations/iso/readiness", response_model=ReadinessOut)
async def readiness(ctx: IsoRead, db: TenantDB) -> ReadinessOut:
    return await iso.readiness(db, ctx)


@router.post("/operations/iso/auditor-invites", response_model=InvitationOut, status_code=CREATED)
async def auditor_invite(body: AuditorInviteIn, ctx: IsoFull, db: TenantDB) -> InvitationOut:
    return await iso.invite_auditor(db, ctx, body)
