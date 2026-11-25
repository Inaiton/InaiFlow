"""Payroll queries only (flush, never commit). Every query filters by ``org_id`` on top of RLS."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from sqlalchemy import Select, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import PageParams, paginate
from app.modules.payroll.models import Employee, PayrollAttendance, PayrollRun, PayrollRunLine, PayrollSettings

POSTED = ("LOCKED_POSTED", "PAID")


async def add(db: AsyncSession, obj: Any) -> Any:
    db.add(obj)
    await db.flush()
    return obj


# ----------------------------------------------------------------- employees
async def list_employees(
    db: AsyncSession, org_id: uuid.UUID, *, q: str | None, category: str | None, include_exited: bool,
    params: PageParams,
) -> tuple[list[Employee], int]:  # fmt: skip
    stmt: Select[Any] = select(Employee).where(Employee.org_id == org_id)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Employee.full_name.ilike(like), Employee.emp_code.ilike(like)))
    if category:
        stmt = stmt.where(Employee.employee_category == category)
    if not include_exited:
        stmt = stmt.where(Employee.is_active.is_(True))
    rows, total = await paginate(db, stmt.order_by(Employee.emp_code), params)
    return [r[0] for r in rows], total


async def get_employee(db: AsyncSession, org_id: uuid.UUID, employee_id: uuid.UUID) -> Employee | None:
    return (
        await db.execute(select(Employee).where(Employee.org_id == org_id, Employee.id == employee_id))
    ).scalar_one_or_none()


async def emp_code_taken(db: AsyncSession, org_id: uuid.UUID, code: str, exclude: uuid.UUID | None = None) -> bool:
    stmt = select(Employee.id).where(Employee.org_id == org_id, func.lower(Employee.emp_code) == code.lower())
    if exclude:
        stmt = stmt.where(Employee.id != exclude)
    return (await db.execute(stmt.limit(1))).first() is not None


async def payable_employees(db: AsyncSession, org_id: uuid.UUID, start: date, end: date) -> list[Employee]:
    """Employees on the rolls for any day of [start, end] (joined on/before end, not exited before start)."""
    stmt = select(Employee).where(
        Employee.org_id == org_id,
        Employee.date_of_joining <= end,
        or_(Employee.date_of_exit.is_(None), Employee.date_of_exit >= start),
    )
    return list((await db.execute(stmt.order_by(Employee.emp_code))).scalars())


async def employees_by_ids(db: AsyncSession, org_id: uuid.UUID, ids: list[uuid.UUID]) -> dict[uuid.UUID, Employee]:
    if not ids:
        return {}
    rows = await db.execute(select(Employee).where(Employee.org_id == org_id, Employee.id.in_(ids)))
    return {e.id: e for e in rows.scalars()}


# ----------------------------------------------------------------- settings
async def get_settings(db: AsyncSession, org_id: uuid.UUID) -> PayrollSettings | None:
    return (await db.execute(select(PayrollSettings).where(PayrollSettings.org_id == org_id))).scalar_one_or_none()


# ----------------------------------------------------------------- attendance
async def attendance_for_month(db: AsyncSession, org_id: uuid.UUID, month: date) -> dict[uuid.UUID, PayrollAttendance]:
    rows = await db.execute(
        select(PayrollAttendance).where(PayrollAttendance.org_id == org_id, PayrollAttendance.month == month)
    )
    return {a.employee_id: a for a in rows.scalars()}


# ----------------------------------------------------------------- runs
async def list_runs(db: AsyncSession, org_id: uuid.UUID) -> list[tuple[PayrollRun, int]]:
    count = (
        select(func.count(PayrollRunLine.id)).where(PayrollRunLine.payroll_run_id == PayrollRun.id).scalar_subquery()
    )
    rows = await db.execute(
        select(PayrollRun, count).where(PayrollRun.org_id == org_id).order_by(PayrollRun.pay_period_month.desc())
    )
    return [(r, int(c)) for r, c in rows.all()]


async def get_run(
    db: AsyncSession, org_id: uuid.UUID, run_id: uuid.UUID, *, for_update: bool = False
) -> PayrollRun | None:
    stmt = select(PayrollRun).where(PayrollRun.org_id == org_id, PayrollRun.id == run_id)
    if for_update:
        stmt = stmt.with_for_update()
    return (await db.execute(stmt)).scalar_one_or_none()


async def run_for_month(db: AsyncSession, org_id: uuid.UUID, month: date) -> PayrollRun | None:
    return (
        await db.execute(select(PayrollRun).where(PayrollRun.org_id == org_id, PayrollRun.pay_period_month == month))
    ).scalar_one_or_none()


async def run_lines(db: AsyncSession, org_id: uuid.UUID, run_id: uuid.UUID) -> list[PayrollRunLine]:
    rows = await db.execute(
        select(PayrollRunLine).where(PayrollRunLine.org_id == org_id, PayrollRunLine.payroll_run_id == run_id)
    )
    return list(rows.scalars())


async def get_line(db: AsyncSession, org_id: uuid.UUID, run_id: uuid.UUID, line_id: uuid.UUID) -> PayrollRunLine | None:
    return (
        await db.execute(
            select(PayrollRunLine).where(
                PayrollRunLine.org_id == org_id, PayrollRunLine.payroll_run_id == run_id, PayrollRunLine.id == line_id
            )
        )
    ).scalar_one_or_none()


async def delete_lines(db: AsyncSession, org_id: uuid.UUID, run_id: uuid.UUID) -> None:
    await db.execute(
        delete(PayrollRunLine).where(PayrollRunLine.org_id == org_id, PayrollRunLine.payroll_run_id == run_id)
    )
    await db.flush()


async def posted_lines_between(db: AsyncSession, org_id: uuid.UUID, start: date, before: date) -> list[PayrollRunLine]:
    """Lines of LOCKED_POSTED/PAID runs with ``start <= month < before`` (YTD inputs for s.192)."""
    rows = await db.execute(
        select(PayrollRunLine)
        .join(PayrollRun, PayrollRun.id == PayrollRunLine.payroll_run_id)
        .where(
            PayrollRun.org_id == org_id,
            PayrollRun.status.in_(POSTED),
            PayrollRun.pay_period_month >= start,
            PayrollRun.pay_period_month < before,
        )
    )
    return list(rows.scalars())
