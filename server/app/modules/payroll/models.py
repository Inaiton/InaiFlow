"""Payroll tables: employees, settings (ledger mapping), monthly attendance, runs and lines."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Date, ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.orm import (
    fk,
    flag,
    jsonb,
    money,
    org_fk,
    pk,
    string,
    ts,
    ts_now,
    uuid_col,
)

DAYS = Numeric(5, 2)
HOURS = Numeric(6, 2)


class Employee(Base):
    __tablename__ = "employees"
    __table_args__ = (UniqueConstraint("org_id", "emp_code"),)

    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = org_fk()
    user_id: Mapped[uuid.UUID | None] = fk("users.id")
    emp_code: Mapped[str] = string(50, nullable=False)
    full_name: Mapped[str] = string(200, nullable=False)
    department: Mapped[str | None] = string(100)
    designation: Mapped[str | None] = string(100)
    employee_category: Mapped[str] = string(30, nullable=False, default="STAFF")
    date_of_joining: Mapped[date] = mapped_column(Date, nullable=False)
    date_of_exit: Mapped[date | None] = mapped_column(Date, nullable=True)
    pan: Mapped[str | None] = string(10)
    uan_epf: Mapped[str | None] = string(20)
    esic_ip_no: Mapped[str | None] = string(20)
    bank_account_no: Mapped[str | None] = string(50)
    bank_ifsc: Mapped[str | None] = string(20)
    tax_regime: Mapped[str] = string(20, nullable=False, default="NEW")
    salary_structure: Mapped[Any] = jsonb(nullable=False)
    is_active: Mapped[bool] = flag(True)
    created_at: Mapped[datetime] = ts_now()


class PayrollSettings(Base):
    __tablename__ = "payroll_settings"

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True
    )
    pt_state_code: Mapped[str | None] = string(5)
    salary_payable_ledger_id: Mapped[uuid.UUID] = fk("ledgers.id", nullable=False)
    direct_wages_ledger_id: Mapped[uuid.UUID] = fk("ledgers.id", nullable=False)
    admin_salary_ledger_id: Mapped[uuid.UUID] = fk("ledgers.id", nullable=False)
    employer_contrib_ledger_id: Mapped[uuid.UUID] = fk("ledgers.id", nullable=False)
    epf_payable_ledger_id: Mapped[uuid.UUID] = fk("ledgers.id", nullable=False)
    esic_payable_ledger_id: Mapped[uuid.UUID] = fk("ledgers.id", nullable=False)
    pt_payable_ledger_id: Mapped[uuid.UUID] = fk("ledgers.id", nullable=False)
    tds_payable_ledger_id: Mapped[uuid.UUID] = fk("ledgers.id", nullable=False)
    default_bank_ledger_id: Mapped[uuid.UUID | None] = fk("ledgers.id")
    working_days_basis: Mapped[str] = string(20, nullable=False, default="CALENDAR")  # CALENDAR | FIXED_26
    updated_at: Mapped[datetime] = ts_now()


class PayrollAttendance(Base):
    __tablename__ = "payroll_attendance"
    __table_args__ = (UniqueConstraint("org_id", "month", "employee_id"),)

    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = org_fk()
    month: Mapped[date] = mapped_column(Date, nullable=False)
    employee_id: Mapped[uuid.UUID] = fk("employees.id", nullable=False, ondelete="CASCADE")
    days_present: Mapped[Decimal] = mapped_column(DAYS, nullable=False, server_default="0")
    lop_days: Mapped[Decimal] = mapped_column(DAYS, nullable=False, server_default="0")
    overtime_hours: Mapped[Decimal] = mapped_column(HOURS, nullable=False, server_default="0")
    production_units: Mapped[Decimal] = money()
    run_allocations: Mapped[Any] = jsonb(nullable=False, default="[]")
    finalized: Mapped[bool] = flag(False)
    updated_at: Mapped[datetime] = ts_now()


class PayrollRun(Base):
    __tablename__ = "payroll_runs"
    __table_args__ = (UniqueConstraint("org_id", "pay_period_month"),)

    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = org_fk()
    pay_period_month: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = string(30, nullable=False, default="DRAFT")  # DRAFT | LOCKED_POSTED | PAID
    total_gross: Mapped[Decimal] = money()
    total_deductions: Mapped[Decimal] = money()
    total_net_pay: Mapped[Decimal] = money()
    total_employer_contrib: Mapped[Decimal] = money()
    posted_voucher_id: Mapped[uuid.UUID | None] = fk("vouchers.id")
    payment_voucher_id: Mapped[uuid.UUID | None] = fk("vouchers.id")
    locked_by: Mapped[uuid.UUID | None] = fk("users.id")
    locked_at: Mapped[datetime | None] = ts()
    created_at: Mapped[datetime] = ts_now()


class PayrollRunLine(Base):
    __tablename__ = "payroll_run_lines"

    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = org_fk()
    payroll_run_id: Mapped[uuid.UUID] = fk("payroll_runs.id", nullable=False, ondelete="CASCADE")
    employee_id: Mapped[uuid.UUID] = fk("employees.id", nullable=False)
    days_worked: Mapped[Decimal] = mapped_column(DAYS, nullable=False)
    lop_days: Mapped[Decimal] = mapped_column(DAYS, nullable=False, server_default="0")
    overtime_hours: Mapped[Decimal] = mapped_column(HOURS, nullable=False, server_default="0")
    earnings_breakdown: Mapped[Any] = jsonb(nullable=False)
    deductions_breakdown: Mapped[Any] = jsonb(nullable=False)
    employer_contrib_breakdown: Mapped[Any] = jsonb(nullable=False)
    net_pay: Mapped[Decimal] = money(default=None)
    period_run_allocations: Mapped[Any] = jsonb(default="[]")
    payslip_doc_id: Mapped[uuid.UUID | None] = uuid_col()
