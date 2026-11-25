"""Payroll DTOs — names and fields exactly as contract section ``payroll``."""

from __future__ import annotations

import re
import uuid
from datetime import date, datetime
from typing import Any

from pydantic import Field, field_validator

from app.core.money import DecimalStr
from app.core.schemas import InModel, OutModel

PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
IFSC_RE = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$")
CATEGORIES = ("SHOP_FLOOR_OPERATOR", "STAFF", "MANAGEMENT")
TAX_REGIMES = ("NEW", "OLD")
WORKING_DAYS_BASES = ("CALENDAR", "FIXED_26", "FIXED_30")
MONTH_PATTERN = r"^\d{4}-(0[1-9]|1[0-2])$"


def _non_negative(v: Any) -> Any:
    if v is not None and v < 0:
        raise ValueError("must not be negative")
    return v


# ----------------------------------------------------------------- employees
class SalaryComponent(InModel):
    name: str = Field(min_length=1, max_length=60)
    amount: DecimalStr

    _nn = field_validator("amount")(_non_negative)


class SalaryStructure(InModel):
    basic: DecimalStr
    da: DecimalStr | None = None
    hra: DecimalStr | None = None
    special: DecimalStr | None = None
    conveyance: DecimalStr | None = None
    other_allowances: list[SalaryComponent] | None = None
    other_deductions: list[SalaryComponent] | None = None
    epf_applicable: bool
    esic_applicable: bool
    pt_applicable: bool
    piece_rate: DecimalStr | None = None
    monthly_tds_override: DecimalStr | None = None

    _nn = field_validator("basic", "da", "hra", "special", "conveyance", "piece_rate", "monthly_tds_override")(
        _non_negative
    )

    @field_validator("other_allowances", "other_deductions")
    @classmethod
    def _unique_names(cls, v: list[SalaryComponent] | None) -> list[SalaryComponent] | None:
        reserved = {"basic", "da", "hra", "special", "conveyance", "overtime", "piece_rate", "epf", "esic", "pt", "tds"}
        names = [c.name for c in v or []]
        if len(set(names)) != len(names):
            raise ValueError("component names must be unique")
        if reserved & {n.lower() for n in names}:
            raise ValueError("component names must not reuse a standard component name")
        return v


class EmployeeIn(InModel):
    emp_code: str = Field(min_length=1, max_length=50)
    full_name: str = Field(min_length=1, max_length=200)
    user_id: uuid.UUID | None = None
    department: str | None = Field(default=None, max_length=100)
    designation: str | None = Field(default=None, max_length=100)
    employee_category: str | None = None
    date_of_joining: date
    pan: str | None = None
    uan_epf: str | None = Field(default=None, max_length=20)
    esic_ip_no: str | None = Field(default=None, max_length=20)
    bank_account_no: str | None = Field(default=None, max_length=50)
    bank_ifsc: str | None = None
    tax_regime: str | None = None
    salary_structure: SalaryStructure

    @field_validator("pan")
    @classmethod
    def _pan(cls, v: str | None) -> str | None:
        if v in (None, ""):
            return None
        v = v.upper()
        if not PAN_RE.match(v):
            raise ValueError("PAN must look like ABCDE1234F")
        return v

    @field_validator("bank_ifsc")
    @classmethod
    def _ifsc(cls, v: str | None) -> str | None:
        if v in (None, ""):
            return None
        v = v.upper()
        if not IFSC_RE.match(v):
            raise ValueError("IFSC must look like HDFC0001234")
        return v

    @field_validator("employee_category")
    @classmethod
    def _category(cls, v: str | None) -> str | None:
        if v is not None and v not in CATEGORIES:
            raise ValueError(f"employee_category must be one of {', '.join(CATEGORIES)}")
        return v

    @field_validator("tax_regime")
    @classmethod
    def _regime(cls, v: str | None) -> str | None:
        if v is not None and v not in TAX_REGIMES:
            raise ValueError("tax_regime must be NEW or OLD")
        return v


class EmployeeExitIn(InModel):
    date_of_exit: date


class EmployeeOut(OutModel):
    id: uuid.UUID
    user_id: uuid.UUID | None
    emp_code: str
    full_name: str
    department: str | None
    designation: str | None
    employee_category: str
    date_of_joining: date
    date_of_exit: date | None
    pan: str | None
    uan_epf: str | None
    esic_ip_no: str | None
    bank_account_no: str | None
    bank_ifsc: str | None
    tax_regime: str
    salary_structure: SalaryStructure
    monthly_gross: DecimalStr
    is_active: bool


# ----------------------------------------------------------------- settings
class PayrollSettingsOut(OutModel):
    pt_state_code: str | None
    salary_payable_ledger_id: uuid.UUID
    direct_wages_ledger_id: uuid.UUID
    admin_salary_ledger_id: uuid.UUID
    employer_contrib_ledger_id: uuid.UUID
    epf_payable_ledger_id: uuid.UUID
    esic_payable_ledger_id: uuid.UUID
    pt_payable_ledger_id: uuid.UUID
    tds_payable_ledger_id: uuid.UUID
    default_bank_ledger_id: uuid.UUID | None
    working_days_basis: str


class PayrollSettingsIn(InModel):
    pt_state_code: str | None = None
    salary_payable_ledger_id: uuid.UUID | None = None
    direct_wages_ledger_id: uuid.UUID | None = None
    admin_salary_ledger_id: uuid.UUID | None = None
    employer_contrib_ledger_id: uuid.UUID | None = None
    epf_payable_ledger_id: uuid.UUID | None = None
    esic_payable_ledger_id: uuid.UUID | None = None
    pt_payable_ledger_id: uuid.UUID | None = None
    tds_payable_ledger_id: uuid.UUID | None = None
    default_bank_ledger_id: uuid.UUID | None = None
    working_days_basis: str | None = None

    @field_validator("working_days_basis")
    @classmethod
    def _basis(cls, v: str | None) -> str | None:
        if v is not None and v not in WORKING_DAYS_BASES:
            raise ValueError(f"working_days_basis must be one of {', '.join(WORKING_DAYS_BASES)}")
        return v


# ----------------------------------------------------------------- attendance
class RunAllocation(InModel):
    period_run_id: uuid.UUID
    share_pct: DecimalStr

    @field_validator("share_pct")
    @classmethod
    def _pct(cls, v: Any) -> Any:
        if v <= 0 or v > 100:
            raise ValueError("share_pct must be > 0 and <= 100")
        return v


class AttendanceRow(OutModel):
    employee_id: uuid.UUID
    emp_code: str
    full_name: str
    employee_category: str
    days_in_month: int
    days_present: DecimalStr
    lop_days: DecimalStr
    overtime_hours: DecimalStr
    production_units: DecimalStr
    run_allocations: list[RunAllocation]
    finalized: bool


class AttendanceRowIn(InModel):
    employee_id: uuid.UUID
    days_present: DecimalStr
    lop_days: DecimalStr
    overtime_hours: DecimalStr | None = None
    production_units: DecimalStr | None = None
    run_allocations: list[RunAllocation] | None = None
    finalized: bool | None = None

    _nn = field_validator("days_present", "lop_days", "overtime_hours", "production_units")(_non_negative)


class AttendanceIn(InModel):
    month: str = Field(pattern=MONTH_PATTERN)
    rows: list[AttendanceRowIn] = Field(max_length=2000)


class AttendanceOut(OutModel):
    month: str
    rows: list[AttendanceRow]
    all_finalized: bool


# ----------------------------------------------------------------- runs
class PayrollRunCreateIn(InModel):
    month: str = Field(pattern=MONTH_PATTERN)


class PayrollLineOut(OutModel):
    id: uuid.UUID
    employee_id: uuid.UUID
    emp_code: str
    full_name: str
    employee_category: str
    days_worked: DecimalStr
    lop_days: DecimalStr
    overtime_hours: DecimalStr
    earnings_breakdown: dict[str, DecimalStr]
    deductions_breakdown: dict[str, DecimalStr]
    employer_contrib_breakdown: dict[str, DecimalStr]
    gross: DecimalStr
    total_deductions: DecimalStr
    net_pay: DecimalStr
    period_run_allocations: Any
    payslip_document_id: uuid.UUID | None


class PayrollRunOut(OutModel):
    id: uuid.UUID
    pay_period_month: date
    status: str
    total_gross: DecimalStr
    total_deductions: DecimalStr
    total_net_pay: DecimalStr
    total_employer_contrib: DecimalStr
    employee_count: int
    posted_voucher_id: uuid.UUID | None
    payment_voucher_id: uuid.UUID | None
    locked_by_name: str | None
    locked_at: datetime | None
    lines: list[PayrollLineOut]


class PayrollRunSummary(OutModel):
    id: uuid.UUID
    pay_period_month: date
    status: str
    total_gross: DecimalStr
    total_net_pay: DecimalStr
    employee_count: int
    locked_at: datetime | None


class MarkPaidIn(InModel):
    bank_ledger_id: uuid.UUID
    payment_date: date
