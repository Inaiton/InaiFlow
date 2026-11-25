"""Taxation routes (contract section "accounts: taxation"). Thin handlers."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile, status

from app.core.context import TenantContext
from app.core.deps import TenantDB, require
from app.core.idempotency import Idem
from app.modules.taxation import service
from app.modules.taxation.schemas import (
    EinvoiceCancelIn,
    EinvoiceOut,
    EwayBillIn,
    Gstr1Out,
    Gstr2bImportOut,
    Gstr2bReconOut,
    Gstr3bOut,
    GstSummaryOut,
    GstValidationIssue,
    TdsChallanOut,
    TdsComputeIn,
    TdsComputeOut,
    TdsSectionOut,
    TdsSummaryRow,
)

router = APIRouter(tags=["taxation"])
T = "/accounts/taxation"
Read = Annotated[TenantContext, Depends(require("accounts.taxation", "READ"))]
Write = Annotated[TenantContext, Depends(require("accounts.taxation", "WRITE"))]
Full = Annotated[TenantContext, Depends(require("accounts.taxation", "FULL"))]


def _file(data: bytes, mime: str, name: str) -> Response:
    return Response(content=data, media_type=mime, headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.get(f"{T}/gst/summary", response_model=GstSummaryOut)
async def gst_summary(ctx: Read, db: TenantDB, period: str = Query()) -> GstSummaryOut:
    return await service.gst_summary(db, ctx, period)


@router.get(f"{T}/gst/gstr1", response_model=Gstr1Out)
async def gstr1(ctx: Read, db: TenantDB, period: str = Query()) -> Gstr1Out:
    return await service.gstr1(db, ctx, period)


@router.get(f"{T}/gst/gstr1/export", response_class=Response)
async def gstr1_export(ctx: Read, db: TenantDB, period: str = Query()) -> Response:
    data, name = await service.gstr1_export(db, ctx, period)
    return _file(data, "application/json", name)


@router.get(f"{T}/gst/gstr3b", response_model=Gstr3bOut)
async def gstr3b(ctx: Read, db: TenantDB, period: str = Query()) -> Gstr3bOut:
    return await service.gstr3b(db, ctx, period)


@router.get(f"{T}/gst/gstr3b/export", response_class=Response)
async def gstr3b_export(ctx: Read, db: TenantDB, period: str = Query()) -> Response:
    data, name = await service.gstr3b_export(db, ctx, period)
    return _file(data, "application/json", name)


@router.get(f"{T}/gst/validate", response_model=list[GstValidationIssue])
async def validate(ctx: Read, db: TenantDB, period: str = Query()) -> list[GstValidationIssue]:
    return await service.validate(db, ctx, period)


@router.post(f"{T}/gst/gstr2b/import", response_model=Gstr2bImportOut, status_code=status.HTTP_201_CREATED)
async def import_2b(ctx: Write, db: TenantDB, period: str = Query(), file: UploadFile = File(...)) -> Gstr2bImportOut:
    return await service.import_2b(db, ctx, period, await file.read(service.MAX_2B_BYTES + 1))


@router.get(f"{T}/gst/gstr2b/reconciliation", response_model=Gstr2bReconOut)
async def reconcile_2b(ctx: Read, db: TenantDB, period: str = Query()) -> Gstr2bReconOut:
    return await service.reconcile_2b(db, ctx, period)


@router.get(f"{T}/einvoice/{{voucher_id}}", response_model=list[EinvoiceOut])
async def list_einvoice(voucher_id: uuid.UUID, ctx: Read, db: TenantDB) -> list[EinvoiceOut]:
    return await service.list_einvoice(db, ctx, voucher_id)


@router.post(f"{T}/einvoice/{{voucher_id}}/generate", response_model=EinvoiceOut)
async def generate_einvoice(voucher_id: uuid.UUID, ctx: Write, db: TenantDB, idem: Idem) -> EinvoiceOut:
    return await idem.save(await service.generate_einvoice(db, ctx, voucher_id))


@router.post(f"{T}/einvoice/{{voucher_id}}/cancel", response_model=EinvoiceOut)
async def cancel_einvoice(voucher_id: uuid.UUID, body: EinvoiceCancelIn, ctx: Full, db: TenantDB) -> EinvoiceOut:
    return await service.cancel_einvoice(db, ctx, voucher_id, body)


@router.post(f"{T}/ewaybill/{{voucher_id}}/generate", response_model=EinvoiceOut)
async def generate_eway(voucher_id: uuid.UUID, body: EwayBillIn, ctx: Write, db: TenantDB, idem: Idem) -> EinvoiceOut:
    return await idem.save(await service.generate_eway(db, ctx, voucher_id, body))


@router.get(f"{T}/tds/sections", response_model=list[TdsSectionOut])
async def tds_sections(ctx: Read, db: TenantDB, on_date: date | None = None) -> list[TdsSectionOut]:
    return await service.tds_sections(db, ctx, on_date)


@router.post(f"{T}/tds/compute", response_model=TdsComputeOut)
async def tds_compute(body: TdsComputeIn, ctx: Read, db: TenantDB) -> TdsComputeOut:
    return await service.tds_compute(db, ctx, body)


@router.get(f"{T}/tds/summary", response_model=list[TdsSummaryRow])
async def tds_summary(
    ctx: Read, db: TenantDB, date_from: date = Query(), date_to: date = Query()
) -> list[TdsSummaryRow]:
    return await service.tds_summary(db, ctx, date_from, date_to)


@router.get(f"{T}/tds/challan", response_model=TdsChallanOut)
async def tds_challan(ctx: Read, db: TenantDB, month: str = Query()) -> TdsChallanOut:
    return await service.tds_challan(db, ctx, month)


@router.get(f"{T}/tds/returns/{{form}}", response_class=Response)
async def tds_return(form: str, ctx: Read, db: TenantDB, quarter: str = Query()) -> Response:
    data, name = await service.tds_return_file(db, ctx, form, quarter)
    return _file(data, "text/plain", name)
