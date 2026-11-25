"""Payroll routes (contract section ``payroll``, all under ``/accounts/payroll``)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.core.context import TenantContext
from app.core.deps import TenantDB, require
from app.core.idempotency import Idem
from app.core.pagination import Page, Paging
from app.modules.payroll import service
from app.modules.payroll.schemas import (
    AttendanceIn,
    AttendanceOut,
    EmployeeExitIn,
    EmployeeIn,
    EmployeeOut,
    MarkPaidIn,
    PayrollRunCreateIn,
    PayrollRunOut,
    PayrollRunSummary,
    PayrollSettingsIn,
    PayrollSettingsOut,
)

router = APIRouter(prefix="/accounts/payroll", tags=["payroll"])
NO_CONTENT = status.HTTP_204_NO_CONTENT

EmpRead = Annotated[TenantContext, Depends(require("accounts.payroll_employees", "READ"))]
EmpWrite = Annotated[TenantContext, Depends(require("accounts.payroll_employees", "WRITE"))]
EmpFull = Annotated[TenantContext, Depends(require("accounts.payroll_employees", "FULL"))]
RunRead = Annotated[TenantContext, Depends(require("accounts.payroll_runs", "READ"))]
RunWrite = Annotated[TenantContext, Depends(require("accounts.payroll_runs", "WRITE"))]
RunFull = Annotated[TenantContext, Depends(require("accounts.payroll_runs", "FULL"))]
MonthQ = Annotated[str, Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")]


def _file(f: service.FileOut) -> Response:
    return Response(f.content, media_type=f.media_type,
                    headers={"Content-Disposition": f'attachment; filename="{f.filename}"'})  # fmt: skip


# ----------------------------------------------------------------- employees
@router.get("/employees", response_model=Page[EmployeeOut])
async def list_employees(
    ctx: EmpRead, db: TenantDB, paging: Paging, q: str | None = None, category: str | None = None,
    include_exited: bool = False,
) -> Page[EmployeeOut]:  # fmt: skip
    return await service.list_employees(db, ctx, q=q, category=category, include_exited=include_exited, params=paging)


@router.post("/employees", response_model=EmployeeOut, status_code=status.HTTP_201_CREATED)
async def create_employee(body: EmployeeIn, ctx: EmpWrite, db: TenantDB, idem: Idem) -> EmployeeOut:
    return await idem.save(await service.create_employee(db, ctx, body), 201)


@router.get("/employees/{employee_id}", response_model=EmployeeOut)
async def get_employee(employee_id: uuid.UUID, ctx: EmpRead, db: TenantDB) -> EmployeeOut:
    return await service.get_employee(db, ctx, employee_id)


@router.patch("/employees/{employee_id}", response_model=EmployeeOut)
async def update_employee(employee_id: uuid.UUID, body: EmployeeIn, ctx: EmpWrite, db: TenantDB) -> EmployeeOut:
    return await service.update_employee(db, ctx, employee_id, body)


@router.post("/employees/{employee_id}/exit", response_model=EmployeeOut)
async def exit_employee(employee_id: uuid.UUID, body: EmployeeExitIn, ctx: EmpFull, db: TenantDB) -> EmployeeOut:
    return await service.exit_employee(db, ctx, employee_id, body)


# ----------------------------------------------------------------- settings
@router.get("/settings", response_model=PayrollSettingsOut)
async def get_settings(ctx: RunRead, db: TenantDB) -> PayrollSettingsOut:
    return await service.get_settings(db, ctx)


@router.put("/settings", response_model=PayrollSettingsOut)
async def put_settings(body: PayrollSettingsIn, ctx: RunFull, db: TenantDB) -> PayrollSettingsOut:
    return await service.update_settings(db, ctx, body)


# ----------------------------------------------------------------- attendance
@router.get("/attendance", response_model=AttendanceOut)
async def get_attendance(ctx: RunRead, db: TenantDB, month: MonthQ) -> AttendanceOut:
    return await service.get_attendance(db, ctx, month)


@router.put("/attendance", response_model=AttendanceOut)
async def put_attendance(body: AttendanceIn, ctx: RunWrite, db: TenantDB) -> AttendanceOut:
    return await service.put_attendance(db, ctx, body)


@router.post("/attendance/pull-operations", response_model=AttendanceOut)
async def pull_operations(ctx: RunWrite, db: TenantDB, month: MonthQ) -> AttendanceOut:
    return await service.pull_operations(db, ctx, month)


# ----------------------------------------------------------------- runs
@router.get("/runs", response_model=list[PayrollRunSummary])
async def list_runs(ctx: RunRead, db: TenantDB) -> list[PayrollRunSummary]:
    return await service.list_runs(db, ctx)


@router.post("/runs", response_model=PayrollRunOut, status_code=status.HTTP_201_CREATED)
async def create_run(body: PayrollRunCreateIn, ctx: RunWrite, db: TenantDB, idem: Idem) -> PayrollRunOut:
    return await idem.save(await service.create_run(db, ctx, body), 201)


@router.get("/runs/{run_id}", response_model=PayrollRunOut)
async def get_run(run_id: uuid.UUID, ctx: RunRead, db: TenantDB) -> PayrollRunOut:
    return await service.get_run(db, ctx, run_id)


@router.post("/runs/{run_id}/recompute", response_model=PayrollRunOut)
async def recompute_run(run_id: uuid.UUID, ctx: RunWrite, db: TenantDB) -> PayrollRunOut:
    return await service.recompute_run(db, ctx, run_id)


@router.post("/runs/{run_id}/lock", response_model=PayrollRunOut)
async def lock_run(run_id: uuid.UUID, ctx: RunFull, db: TenantDB, idem: Idem) -> PayrollRunOut:
    return await idem.save(await service.lock_run(db, ctx, run_id))


@router.post("/runs/{run_id}/mark-paid", response_model=PayrollRunOut)
async def mark_paid(run_id: uuid.UUID, body: MarkPaidIn, ctx: RunFull, db: TenantDB, idem: Idem) -> PayrollRunOut:
    return await idem.save(await service.mark_paid(db, ctx, run_id, body))


@router.delete("/runs/{run_id}", status_code=NO_CONTENT)
async def delete_run(run_id: uuid.UUID, ctx: RunFull, db: TenantDB) -> Response:
    await service.delete_run(db, ctx, run_id)
    return Response(status_code=NO_CONTENT)


# ----------------------------------------------------------------- files
@router.get("/runs/{run_id}/bank-file")
async def bank_file(run_id: uuid.UUID, ctx: RunFull, db: TenantDB, format: str | None = None) -> Response:  # noqa: A002
    return _file(await service.bank_file(db, ctx, run_id, format))


@router.get("/runs/{run_id}/payslips/{line_id}")
async def payslip(run_id: uuid.UUID, line_id: uuid.UUID, ctx: RunRead, db: TenantDB) -> Response:
    return _file(await service.payslip(db, ctx, run_id, line_id))


@router.get("/runs/{run_id}/statutory/{kind}")
async def statutory(run_id: uuid.UUID, kind: str, ctx: RunRead, db: TenantDB) -> Response:
    return _file(await service.statutory_file(db, ctx, run_id, kind))
