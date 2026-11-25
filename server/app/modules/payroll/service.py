"""Payroll business rules: employees, settings, attendance, runs (compute / lock / pay) and payroll files.

Cross-module work goes through interfaces only: accounts (vouchers, ledgers), operations (period-run cost
allocation, step executions), documents (month folders, generated payslips), organization, identity, platform.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.storage import get_storage
from app.core.audit import write_audit
from app.core.context import TenantContext
from app.core.errors import (
    AlreadyExistsError,
    DoubleEntryImbalanceError,
    InvalidStateError,
    NotFoundError,
    PayrollNotReadyError,
    ValidationFailedError,
)
from app.core.fy import format_month, fy_for_date, month_end, parse_month
from app.core.money import ZERO, D, q2, q4, to_str
from app.core.pagination import Page, PageParams
from app.modules.accounts import interface as accounts
from app.modules.documents import interface as documents
from app.modules.identity import interface as identity
from app.modules.operations import interface as operations
from app.modules.organization import interface as organization
from app.modules.payroll import calc, exports
from app.modules.payroll import repository as repo
from app.modules.payroll.models import Employee, PayrollAttendance, PayrollRun, PayrollRunLine, PayrollSettings
from app.modules.payroll.schemas import (
    AttendanceIn,
    AttendanceOut,
    AttendanceRow,
    EmployeeExitIn,
    EmployeeIn,
    EmployeeOut,
    MarkPaidIn,
    PayrollLineOut,
    PayrollRunCreateIn,
    PayrollRunOut,
    PayrollRunSummary,
    PayrollSettingsIn,
    PayrollSettingsOut,
    RunAllocation,
)
from app.modules.platform.interface import get_config
from app.seeds.default_ledgers import DEFAULT_LEDGERS

MODULE = "ACCOUNTS"
OPERATOR = "SHOP_FLOOR_OPERATOR"
DRAFT, LOCKED, PAID = "DRAFT", "LOCKED_POSTED", "PAID"
HUNDRED = Decimal(100)
SYSTEM_LEDGER_CODES = [d["system_code"] for d in DEFAULT_LEDGERS if d.get("system_code")]
LEDGER_FIELDS = (
    "salary_payable_ledger_id", "direct_wages_ledger_id", "admin_salary_ledger_id", "employer_contrib_ledger_id",
    "epf_payable_ledger_id", "esic_payable_ledger_id", "pt_payable_ledger_id", "tds_payable_ledger_id",
    "default_bank_ledger_id",
)  # fmt: skip
STATUTORY_KINDS = {"epf-ecr": "text/plain", "esic": "text/csv", "pt": "text/csv"}


def _month(value: str) -> date:
    try:
        return parse_month(value)
    except ValueError as exc:
        raise ValidationFailedError(str(exc)) from exc


def _field(obj: Any, *names: str) -> Any:
    """Read a field from an interface DTO that may be a dataclass/ORM object or a dict."""
    for n in names:
        if isinstance(obj, dict) and n in obj:
            return obj[n]
        if hasattr(obj, n):
            return getattr(obj, n)
    return None


def _dec_map(data: dict[str, Any] | None) -> dict[str, Decimal]:
    return {k: D(v) for k, v in (data or {}).items()}


def _str_map(data: dict[str, Decimal]) -> dict[str, str]:
    return {k: to_str(v) or "0.00" for k, v in data.items()}


async def _assert_ledgers(db: AsyncSession, ctx: TenantContext, ids: list[uuid.UUID | None]) -> None:
    """Every id must be a ledger of this org (system ledgers, or any ledger known to accounts.resource_names)."""
    wanted = {i for i in ids if i}
    if not wanted:
        return
    known = set((await accounts.get_ledger_ids_by_code(db, ctx, SYSTEM_LEDGER_CODES)).values())
    rest = wanted - known
    if rest:
        known |= set((await accounts.resource_names(db, ctx, "LEDGER", list(rest))).keys())
    bad = sorted(str(i) for i in wanted - known)
    if bad:
        raise ValidationFailedError("Unknown ledger", {"ledger_ids": bad})


# ================================================================= employees
def employee_out(e: Employee) -> EmployeeOut:
    data = {k: getattr(e, k) for k in EmployeeOut.model_fields if k != "monthly_gross"}
    data["monthly_gross"] = calc.monthly_gross(calc.parse_structure(e.salary_structure))
    return EmployeeOut.model_validate(data)


async def list_employees(
    db: AsyncSession, ctx: TenantContext, *, q: str | None, category: str | None, include_exited: bool,
    params: PageParams,
) -> Page[EmployeeOut]:  # fmt: skip
    rows, total = await repo.list_employees(db, ctx.org_id, q=q, category=category, include_exited=include_exited,
                                            params=params)  # fmt: skip
    return Page(items=[employee_out(e) for e in rows], total=total, limit=params.limit, offset=params.offset)


async def _employee(db: AsyncSession, ctx: TenantContext, employee_id: uuid.UUID) -> Employee:
    e = await repo.get_employee(db, ctx.org_id, employee_id)
    if e is None:
        raise NotFoundError()
    return e


async def get_employee(db: AsyncSession, ctx: TenantContext, employee_id: uuid.UUID) -> EmployeeOut:
    return employee_out(await _employee(db, ctx, employee_id))


async def _validate_employee(db: AsyncSession, ctx: TenantContext, body: EmployeeIn, exclude: uuid.UUID | None) -> None:
    if await repo.emp_code_taken(db, ctx.org_id, body.emp_code, exclude):
        raise AlreadyExistsError("An employee with this code already exists", {"field": "emp_code"})
    if body.user_id is not None and not await organization.is_member(db, ctx.org_id, body.user_id):
        raise ValidationFailedError("The linked user is not a member of this organization", {"field": "user_id"})


def _employee_values(body: EmployeeIn, *, creating: bool) -> dict[str, Any]:
    data = body.model_dump(mode="python", exclude={"salary_structure"}, exclude_unset=not creating)
    for key, default in (("employee_category", "STAFF"), ("tax_regime", "NEW")):
        if data.get(key) is None and (creating or key in data):
            data[key] = default
    data["salary_structure"] = body.salary_structure.model_dump(mode="json", exclude_none=True)
    return data


async def create_employee(db: AsyncSession, ctx: TenantContext, body: EmployeeIn) -> EmployeeOut:
    await _validate_employee(db, ctx, body, None)
    e = await repo.add(db, Employee(org_id=ctx.org_id, **_employee_values(body, creating=True)))
    await write_audit(db, ctx, MODULE, "CREATE", "employee", e.id, after=e.to_dict())
    return employee_out(e)


async def update_employee(
    db: AsyncSession, ctx: TenantContext, employee_id: uuid.UUID, body: EmployeeIn
) -> EmployeeOut:
    e = await _employee(db, ctx, employee_id)
    await _validate_employee(db, ctx, body, e.id)
    before = e.to_dict()
    for k, v in _employee_values(body, creating=False).items():
        setattr(e, k, v)
    await db.flush()
    await write_audit(db, ctx, MODULE, "UPDATE", "employee", e.id, before=before, after=e.to_dict(), changed_only=True)
    return employee_out(e)


async def exit_employee(
    db: AsyncSession, ctx: TenantContext, employee_id: uuid.UUID, body: EmployeeExitIn
) -> EmployeeOut:
    e = await _employee(db, ctx, employee_id)
    if e.date_of_exit is not None:
        raise InvalidStateError("The employee has already exited")
    if body.date_of_exit < e.date_of_joining:
        raise ValidationFailedError("Exit date is before the joining date", {"field": "date_of_exit"})
    before = e.to_dict()
    e.date_of_exit, e.is_active = body.date_of_exit, False
    await db.flush()
    await write_audit(db, ctx, MODULE, "UPDATE", "employee", e.id, before=before, after=e.to_dict(),
                      reason="exit", changed_only=True)  # fmt: skip
    return employee_out(e)


# ================================================================= settings
async def _settings(db: AsyncSession, ctx: TenantContext) -> PayrollSettings:
    s = await repo.get_settings(db, ctx.org_id)
    if s is None:
        raise NotFoundError("Payroll settings are not configured")
    return s


async def get_settings(db: AsyncSession, ctx: TenantContext) -> PayrollSettingsOut:
    return PayrollSettingsOut.model_validate(await _settings(db, ctx))


async def update_settings(db: AsyncSession, ctx: TenantContext, body: PayrollSettingsIn) -> PayrollSettingsOut:
    s = await _settings(db, ctx)
    changes = body.model_dump(exclude_unset=True)
    for key in LEDGER_FIELDS[:-1]:
        if key in changes and changes[key] is None:
            raise ValidationFailedError(f"{key} cannot be cleared", {"field": key})
    await _assert_ledgers(db, ctx, [changes.get(k) for k in LEDGER_FIELDS])
    if changes.get("pt_state_code") is not None:
        states = (await get_config(db, "PAYROLL_STATUTORY", "PT_SLABS"))["states"]
        if changes["pt_state_code"] not in states:
            raise ValidationFailedError("No professional tax slabs are configured for this state",
                                        {"field": "pt_state_code", "supported": sorted(states)})  # fmt: skip
    before = s.to_dict()
    for k, v in changes.items():
        setattr(s, k, v)
    s.updated_at = datetime.now(UTC)
    await db.flush()
    await write_audit(db, ctx, MODULE, "UPDATE", "payroll_settings", ctx.org_id, before=before, after=s.to_dict(),
                      changed_only=True)  # fmt: skip
    return PayrollSettingsOut.model_validate(s)


# ================================================================= attendance
def _default_lop(e: Employee, month: date) -> Decimal:
    """Days of the month before joining / after exit."""
    start, end = month, month_end(month)
    lop = 0
    if e.date_of_joining > start:
        lop += (min(e.date_of_joining, end) - start).days
    if e.date_of_exit and e.date_of_exit < end:
        lop += (end - max(e.date_of_exit, start)).days
    return D(min(lop, calc.days_in_month(month)))


def _row(e: Employee, a: PayrollAttendance | None, month: date) -> AttendanceRow:
    dim = calc.days_in_month(month)
    if a is None:
        lop = _default_lop(e, month)
        return AttendanceRow(employee_id=e.id, emp_code=e.emp_code, full_name=e.full_name,
                             employee_category=e.employee_category, days_in_month=dim, days_present=D(dim) - lop,
                             lop_days=lop, overtime_hours=ZERO, production_units=ZERO, run_allocations=[],
                             finalized=False)  # fmt: skip
    return AttendanceRow(employee_id=e.id, emp_code=e.emp_code, full_name=e.full_name,
                         employee_category=e.employee_category, days_in_month=dim, days_present=a.days_present,
                         lop_days=a.lop_days, overtime_hours=a.overtime_hours, production_units=a.production_units,
                         run_allocations=[RunAllocation.model_validate(r) for r in a.run_allocations or []],
                         finalized=a.finalized)  # fmt: skip


async def _attendance_out(db: AsyncSession, ctx: TenantContext, month: date) -> AttendanceOut:
    employees = await repo.payable_employees(db, ctx.org_id, month, month_end(month))
    att = await repo.attendance_for_month(db, ctx.org_id, month)
    rows = [_row(e, att.get(e.id), month) for e in employees]
    return AttendanceOut(
        month=format_month(month), rows=rows, all_finalized=bool(rows) and all(r.finalized for r in rows)
    )


async def get_attendance(db: AsyncSession, ctx: TenantContext, month: str) -> AttendanceOut:
    return await _attendance_out(db, ctx, _month(month))


async def _assert_month_open(db: AsyncSession, ctx: TenantContext, month: date) -> None:
    run = await repo.run_for_month(db, ctx.org_id, month)
    if run is not None and run.status != DRAFT:
        raise InvalidStateError("Payroll for this month is already locked")


async def _validate_allocations(db: AsyncSession, ctx: TenantContext, allocations: list[RunAllocation]) -> None:
    if not allocations:
        return
    ids = [a.period_run_id for a in allocations]
    if len(set(ids)) != len(ids):
        raise ValidationFailedError("A period run appears twice in run_allocations")
    total = sum((a.share_pct for a in allocations), ZERO)
    if total != HUNDRED:
        raise ValidationFailedError("run_allocations must total 100%", {"total": to_str(total)})
    known = await operations.resource_names(db, ctx, "PERIOD_RUN", ids)
    missing = [str(i) for i in ids if i not in known]
    if missing:
        raise ValidationFailedError("Unknown period run", {"period_run_ids": missing})


async def put_attendance(db: AsyncSession, ctx: TenantContext, body: AttendanceIn) -> AttendanceOut:
    month = _month(body.month)
    await _assert_month_open(db, ctx, month)
    employees = {e.id: e for e in await repo.payable_employees(db, ctx.org_id, month, month_end(month))}
    existing = await repo.attendance_for_month(db, ctx.org_id, month)
    dim = D(calc.days_in_month(month))
    for r in body.rows:
        e = employees.get(r.employee_id)
        if e is None:
            raise ValidationFailedError("Employee is not on the rolls for this month",
                                        {"employee_id": str(r.employee_id)})  # fmt: skip
        if r.days_present + r.lop_days > dim:
            raise ValidationFailedError("days_present + lop_days exceeds the days in the month",
                                        {"employee_id": str(r.employee_id)})  # fmt: skip
        allocations = r.run_allocations
        if allocations is not None:
            if allocations and e.employee_category != OPERATOR:
                raise ValidationFailedError("Only shop-floor operators can be allocated to period runs",
                                            {"employee_id": str(r.employee_id)})  # fmt: skip
            await _validate_allocations(db, ctx, allocations)
        a = existing.get(r.employee_id)
        if a is None:
            a = await repo.add(db, PayrollAttendance(org_id=ctx.org_id, month=month, employee_id=r.employee_id,
                                                     run_allocations=[], production_units=ZERO))  # fmt: skip
        before = a.to_dict()
        a.days_present, a.lop_days = r.days_present, r.lop_days
        if r.overtime_hours is not None:
            a.overtime_hours = r.overtime_hours
        if r.production_units is not None:
            a.production_units = r.production_units
        if allocations is not None:
            a.run_allocations = [x.model_dump(mode="json") for x in allocations]
        if r.finalized is not None:
            a.finalized = r.finalized
        a.updated_at = datetime.now(UTC)
        await db.flush()
        await write_audit(db, ctx, MODULE, "UPDATE", "payroll_attendance", a.id, before=before, after=a.to_dict(),
                          changed_only=True)  # fmt: skip
    return await _attendance_out(db, ctx, month)


def _shares(counts: dict[uuid.UUID, int]) -> list[dict[str, str]]:
    total = sum(counts.values())
    ordered = sorted(counts.items(), key=lambda kv: (-kv[1], str(kv[0])))
    pcts = [q4(D(c) * HUNDRED / D(total)) for _, c in ordered[:-1]]
    pcts.append(HUNDRED - sum(pcts, ZERO))
    return [
        {"period_run_id": str(rid), "share_pct": to_str(p) or "0"} for (rid, _), p in zip(ordered, pcts, strict=True)
    ]


async def pull_operations(db: AsyncSession, ctx: TenantContext, month: str) -> AttendanceOut:
    """Suggest run_allocations for operators from the steps they executed this month (share by step count).

    Saved on non-finalized rows only; never finalizes."""
    m = _month(month)
    await _assert_month_open(db, ctx, m)
    executions = await operations.list_step_executions_by_month(db, ctx, m)
    per_user: dict[uuid.UUID, dict[uuid.UUID, int]] = defaultdict(lambda: defaultdict(int))
    for ex in executions:
        user_id, run_id = _field(ex, "executed_by", "user_id"), _field(ex, "period_run_id", "run_id")
        if user_id and run_id:
            per_user[uuid.UUID(str(user_id))][uuid.UUID(str(run_id))] += 1
    existing = await repo.attendance_for_month(db, ctx.org_id, m)
    for e in await repo.payable_employees(db, ctx.org_id, m, month_end(m)):
        if e.employee_category != OPERATOR or e.user_id is None or not per_user.get(e.user_id):
            continue
        a = existing.get(e.id)
        if a is not None and a.finalized:
            continue
        if a is None:
            row = _row(e, None, m)
            a = await repo.add(db, PayrollAttendance(org_id=ctx.org_id, month=m, employee_id=e.id,
                                                     days_present=row.days_present, lop_days=row.lop_days,
                                                     production_units=ZERO, run_allocations=[]))  # fmt: skip
        a.run_allocations = _shares(per_user[e.user_id])
        a.updated_at = datetime.now(UTC)
    await db.flush()
    return await _attendance_out(db, ctx, m)


# ================================================================= runs: compute
@dataclass(slots=True)
class _Computed:
    employee: Employee
    attendance: PayrollAttendance | None
    result: calc.LineResult
    allocations: list[dict[str, Any]]


async def _statutory(db: AsyncSession, on: date) -> calc.StatutoryConfig:
    async def cfg(key: str) -> dict:
        return await get_config(db, "PAYROLL_STATUTORY", key, on_date=on)

    return calc.StatutoryConfig(epf=await cfg("EPF"), esic=await cfg("ESIC"), pt_slabs=await cfg("PT_SLABS"),
                                income_tax=await cfg("INCOME_TAX"))  # fmt: skip


async def _org(db: AsyncSession, ctx: TenantContext) -> Any:
    org = await organization.get_org_brief(db, ctx.org_id)
    if org is None:
        raise NotFoundError()
    return org


async def _prior_ytd(
    db: AsyncSession, ctx: TenantContext, month: date, fy_start: date
) -> dict[uuid.UUID, calc.PriorYtd]:
    sums: dict[uuid.UUID, dict[str, Decimal]] = defaultdict(lambda: defaultdict(lambda: ZERO))
    for ln in await repo.posted_lines_between(db, ctx.org_id, fy_start, month):
        s = sums[ln.employee_id]
        s["gross"] += sum(_dec_map(ln.earnings_breakdown).values(), ZERO)
        ded = _dec_map(ln.deductions_breakdown)
        for k in ("tds", "epf", "pt"):
            s[k] += ded.get(k, ZERO)
    return {k: calc.PriorYtd(**v) for k, v in sums.items()}


async def _compute(db: AsyncSession, ctx: TenantContext, run: PayrollRun, *, strict: bool) -> list[_Computed]:
    settings = await _settings(db, ctx)
    org = await _org(db, ctx)
    month, end = run.pay_period_month, month_end(run.pay_period_month)
    cfg = await _statutory(db, end)
    fy = fy_for_date(month, org.fy_begins_from)
    remaining = calc.remaining_fy_months(month, fy.start)
    basis = calc.basis_days(settings.working_days_basis, month)
    prior = await _prior_ytd(db, ctx, month, fy.start)
    att = await repo.attendance_for_month(db, ctx.org_id, month)
    out: list[_Computed] = []
    for e in await repo.payable_employees(db, ctx.org_id, month, end):
        a = att.get(e.id)
        row = _row(e, a, month)
        inp = calc.LineInput(
            structure=calc.parse_structure(e.salary_structure),
            attendance=calc.AttendanceInput(row.days_present, row.lop_days, row.overtime_hours, row.production_units),
            tax_regime=e.tax_regime, month=month, basis_days=basis, remaining_months=remaining,
            pt_state_code=settings.pt_state_code, prior=prior.get(e.id, calc.PriorYtd()),
        )  # fmt: skip
        out.append(_Computed(e, a, calc.compute_line(inp, cfg), []))
    calc.apply_admin_minimum([c.result for c in out], cfg.epf)
    for c in out:
        allocs = (c.attendance.run_allocations if c.attendance else None) or []
        if c.employee.employee_category != OPERATOR or not allocs:
            continue
        shares = [D(x["share_pct"]) for x in allocs]
        if sum(shares, ZERO) != HUNDRED:
            if strict:
                raise ValidationFailedError("run_allocations must total 100%", {"employee_id": str(c.employee.id)})
            continue
        amounts = calc.split_by_share(c.result.gross, shares)
        c.allocations = [{"period_run_id": x["period_run_id"], "share_pct": to_str(D(x["share_pct"])),
                          "amount": to_str(amt)} for x, amt in zip(allocs, amounts, strict=True)]  # fmt: skip
    return out


async def _store_lines(db: AsyncSession, ctx: TenantContext, run: PayrollRun, computed: list[_Computed]) -> None:
    await repo.delete_lines(db, ctx.org_id, run.id)
    for c in computed:
        r = c.result
        db.add(PayrollRunLine(
            org_id=ctx.org_id, payroll_run_id=run.id, employee_id=c.employee.id,
            days_worked=q2(c.attendance.days_present if c.attendance else _row(c.employee, None, run.pay_period_month).days_present),
            lop_days=q2(c.attendance.lop_days if c.attendance else _default_lop(c.employee, run.pay_period_month)),
            overtime_hours=q2(c.attendance.overtime_hours if c.attendance else ZERO),
            earnings_breakdown=_str_map(r.earnings), deductions_breakdown=_str_map(r.deductions),
            employer_contrib_breakdown=_str_map(r.employer), net_pay=r.net_pay, period_run_allocations=c.allocations,
        ))  # fmt: skip
    run.total_gross = q2(sum((c.result.gross for c in computed), ZERO))
    run.total_deductions = q2(sum((c.result.total_deductions for c in computed), ZERO))
    run.total_net_pay = q2(sum((c.result.net_pay for c in computed), ZERO))
    run.total_employer_contrib = q2(sum((c.result.employer_total for c in computed), ZERO))
    await db.flush()


async def _run_out(db: AsyncSession, ctx: TenantContext, run: PayrollRun) -> PayrollRunOut:
    lines = await repo.run_lines(db, ctx.org_id, run.id)
    emps = await repo.employees_by_ids(db, ctx.org_id, [ln.employee_id for ln in lines])
    locked_by = (await identity.user_briefs(db, [run.locked_by])).get(run.locked_by) if run.locked_by else None
    out_lines = []
    for ln in sorted(lines, key=lambda x: emps[x.employee_id].emp_code):
        e = emps[ln.employee_id]
        earn, ded = _dec_map(ln.earnings_breakdown), _dec_map(ln.deductions_breakdown)
        gross, total_ded = q2(sum(earn.values(), ZERO)), q2(sum(ded.values(), ZERO))
        out_lines.append(PayrollLineOut(
            id=ln.id, employee_id=e.id, emp_code=e.emp_code, full_name=e.full_name,
            employee_category=e.employee_category, days_worked=ln.days_worked, lop_days=ln.lop_days,
            overtime_hours=ln.overtime_hours, earnings_breakdown=earn, deductions_breakdown=ded,
            employer_contrib_breakdown=_dec_map(ln.employer_contrib_breakdown), gross=gross,
            total_deductions=total_ded, net_pay=ln.net_pay, period_run_allocations=ln.period_run_allocations or [],
            payslip_document_id=ln.payslip_doc_id,
        ))  # fmt: skip
    return PayrollRunOut(
        id=run.id, pay_period_month=run.pay_period_month, status=run.status, total_gross=run.total_gross,
        total_deductions=run.total_deductions, total_net_pay=run.total_net_pay,
        total_employer_contrib=run.total_employer_contrib, employee_count=len(lines),
        posted_voucher_id=run.posted_voucher_id, payment_voucher_id=run.payment_voucher_id,
        locked_by_name=locked_by.full_name if locked_by else None, locked_at=run.locked_at, lines=out_lines,
    )  # fmt: skip


# ================================================================= runs: CRUD
async def list_runs(db: AsyncSession, ctx: TenantContext) -> list[PayrollRunSummary]:
    return [
        PayrollRunSummary(
            id=r.id,
            pay_period_month=r.pay_period_month,
            status=r.status,
            total_gross=r.total_gross,
            total_net_pay=r.total_net_pay,
            employee_count=n,
            locked_at=r.locked_at,
        )  # fmt: skip
        for r, n in await repo.list_runs(db, ctx.org_id)
    ]


async def _run(db: AsyncSession, ctx: TenantContext, run_id: uuid.UUID, *, for_update: bool = False) -> PayrollRun:
    run = await repo.get_run(db, ctx.org_id, run_id, for_update=for_update)
    if run is None:
        raise NotFoundError()
    return run


async def get_run(db: AsyncSession, ctx: TenantContext, run_id: uuid.UUID) -> PayrollRunOut:
    return await _run_out(db, ctx, await _run(db, ctx, run_id))


async def create_run(db: AsyncSession, ctx: TenantContext, body: PayrollRunCreateIn) -> PayrollRunOut:
    month = _month(body.month)
    if await repo.run_for_month(db, ctx.org_id, month) is not None:
        raise AlreadyExistsError("A payroll run already exists for this month")
    run = await repo.add(db, PayrollRun(org_id=ctx.org_id, pay_period_month=month, status=DRAFT))
    await _store_lines(db, ctx, run, await _compute(db, ctx, run, strict=False))
    await write_audit(db, ctx, MODULE, "CREATE", "payroll_run", run.id, after=run.to_dict())
    return await _run_out(db, ctx, run)


async def recompute_run(db: AsyncSession, ctx: TenantContext, run_id: uuid.UUID) -> PayrollRunOut:
    run = await _run(db, ctx, run_id, for_update=True)
    if run.status != DRAFT:
        raise InvalidStateError("Only draft payroll runs can be recomputed")
    before = run.to_dict()
    await _store_lines(db, ctx, run, await _compute(db, ctx, run, strict=False))
    await write_audit(db, ctx, MODULE, "UPDATE", "payroll_run", run.id, before=before, after=run.to_dict(),
                      reason="recompute", changed_only=True)  # fmt: skip
    return await _run_out(db, ctx, run)


async def delete_run(db: AsyncSession, ctx: TenantContext, run_id: uuid.UUID) -> None:
    run = await _run(db, ctx, run_id, for_update=True)
    if run.status != DRAFT:
        raise InvalidStateError("Only draft payroll runs can be deleted")
    before = run.to_dict()
    await repo.delete_lines(db, ctx.org_id, run.id)
    await db.delete(run)
    await db.flush()
    await write_audit(db, ctx, MODULE, "DELETE", "payroll_run", run_id, before=before)


# ================================================================= runs: lock & pay
def build_payroll_entries(
    computed: list[_Computed], settings: PayrollSettings, cost_centres: dict[uuid.UUID, uuid.UUID | None]
) -> list[accounts.SystemEntry]:
    """Balanced PAYROLL voucher lines (plan §3.8). Zero amounts are dropped."""
    direct: dict[uuid.UUID | None, Decimal] = defaultdict(lambda: ZERO)
    admin = employer = net = epf = esic = pt = tds = ZERO
    for c in computed:
        r = c.result
        if c.employee.employee_category == OPERATOR:
            allocated = ZERO
            for a in c.allocations:
                amount = D(a["amount"])
                direct[cost_centres.get(uuid.UUID(str(a["period_run_id"])))] += amount
                allocated += amount
            direct[None] += r.gross - allocated
        else:
            admin += r.gross
        employer += r.employer_total
        net += r.net_pay + r.other_deductions_total
        epf += r.deductions.get("epf", ZERO) + sum((r.employer.get(k, ZERO) for k in ("eps", "epf_er", "edli",
                                                                                     "epf_admin")), ZERO)  # fmt: skip
        esic += r.deductions.get("esic", ZERO) + r.employer.get("esic_er", ZERO)
        pt += r.deductions.get("pt", ZERO)
        tds += r.deductions.get("tds", ZERO)
    E = accounts.SystemEntry  # noqa: N806
    entries = [E(settings.direct_wages_ledger_id, "DR", q2(v), cost_centre_id=cc) for cc, v in direct.items()]
    entries += [
        E(settings.admin_salary_ledger_id, "DR", q2(admin)),
        E(settings.employer_contrib_ledger_id, "DR", q2(employer)),
        E(settings.salary_payable_ledger_id, "CR", q2(net)),
        E(settings.epf_payable_ledger_id, "CR", q2(epf)),
        E(settings.esic_payable_ledger_id, "CR", q2(esic)),
        E(settings.pt_payable_ledger_id, "CR", q2(pt)),
        E(settings.tds_payable_ledger_id, "CR", q2(tds)),
    ]
    entries = [e for e in entries if e.amount != 0]
    dr = sum((e.amount for e in entries if e.entry_type == "DR"), ZERO)
    cr = sum((e.amount for e in entries if e.entry_type == "CR"), ZERO)
    if dr != cr:
        raise DoubleEntryImbalanceError("Payroll voucher does not balance", {"debit": to_str(dr), "credit": to_str(cr)})
    return entries


def _slip(c: Employee, ln: PayrollRunLine, month: date, epf_cfg: dict[str, Any]) -> exports.SlipLine:
    earn, ded, er = (
        _dec_map(ln.earnings_breakdown),
        _dec_map(ln.deductions_breakdown),
        _dec_map(ln.employer_contrib_breakdown),
    )
    epf_wages = calc.compute_epf(earn, epf_cfg).epf_wages if ded.get("epf") else ZERO
    return exports.SlipLine(
        emp_code=c.emp_code, full_name=c.full_name, designation=c.designation, department=c.department, pan=c.pan,
        uan_epf=c.uan_epf, esic_ip_no=c.esic_ip_no, bank_account_no=c.bank_account_no, bank_ifsc=c.bank_ifsc,
        days_in_month=calc.days_in_month(month), days_worked=ln.days_worked, lop_days=ln.lop_days, earnings=earn,
        deductions=ded, employer=er, gross=q2(sum(earn.values(), ZERO)), total_deductions=q2(sum(ded.values(), ZERO)),
        net_pay=ln.net_pay, epf_wages=epf_wages, eps_wages=epf_wages if er.get("eps") else ZERO, edli_wages=epf_wages,
    )  # fmt: skip


async def lock_run(db: AsyncSession, ctx: TenantContext, run_id: uuid.UUID) -> PayrollRunOut:
    """One transaction (spec 09 §2C / plan §3.8): readiness -> compute -> allocate -> voucher -> payslips."""
    run = await _run(db, ctx, run_id, for_update=True)
    if run.status != DRAFT:
        raise InvalidStateError("Only draft payroll runs can be locked")
    month, end = run.pay_period_month, month_end(run.pay_period_month)
    employees = await repo.payable_employees(db, ctx.org_id, month, end)
    if not employees:
        raise PayrollNotReadyError("There are no employees on the rolls for this month", {"missing": []})
    att = await repo.attendance_for_month(db, ctx.org_id, month)
    missing = [e for e in employees if e.id not in att or not att[e.id].finalized]
    if missing:
        raise PayrollNotReadyError("Attendance is not finalized for every employee", {"missing": [
            {"employee_id": str(e.id), "emp_code": e.emp_code, "full_name": e.full_name} for e in missing]})  # fmt: skip
    before = run.to_dict()
    settings = await _settings(db, ctx)
    computed = await _compute(db, ctx, run, strict=True)
    await _store_lines(db, ctx, run, computed)

    per_run: dict[uuid.UUID, Decimal] = defaultdict(lambda: ZERO)
    for c in computed:
        for a in c.allocations:
            per_run[uuid.UUID(str(a["period_run_id"]))] += D(a["amount"])
    cost_centres: dict[uuid.UUID, uuid.UUID | None] = {}
    if per_run:
        runs = await operations.get_runs_by_ids(db, ctx, list(per_run))
        cost_centres = {uuid.UUID(str(_field(r, "id"))): _field(r, "cost_centre_id") for r in runs}
        unknown = [str(i) for i in per_run if i not in cost_centres]
        if unknown:
            raise ValidationFailedError("Unknown period run in allocations", {"period_run_ids": unknown})
        for rid, amount in per_run.items():
            await operations.apply_payroll_allocation(db, ctx, rid, q2(amount))

    entries = build_payroll_entries(computed, settings, cost_centres)
    label = exports.month_label(month)
    voucher_id = await accounts.post_system_voucher(db, ctx, base_type="PAYROLL", voucher_date=end, entries=entries,
                                                    narration=f"Payroll for {label}")  # fmt: skip

    org = await _org(db, ctx)
    epf_cfg = (await _statutory(db, end)).epf
    folders = await documents.ensure_month_folders(db, ctx, month)
    emps = {c.employee.id: c.employee for c in computed}
    for ln in await repo.run_lines(db, ctx.org_id, run.id):
        e = emps[ln.employee_id]
        pdf = exports.render_payslip(org, _slip(e, ln, month, epf_cfg), month)
        ln.payslip_doc_id = await documents.store_generated_file(
            db, ctx, folder_id=folders.payroll_id, title=f"Payslip {e.emp_code} {e.full_name} - {label}",
            mime="application/pdf", data=pdf, source_type="AUTO_PAYSLIP",
            file_name=f"payslip-{e.emp_code}-{format_month(month)}.pdf", linked_voucher_id=voucher_id,
        )  # fmt: skip

    run.status, run.posted_voucher_id = LOCKED, voucher_id
    run.locked_by, run.locked_at = ctx.user_id, datetime.now(UTC)
    await db.flush()
    await write_audit(db, ctx, MODULE, "LOCK", "payroll_run", run.id, before=before, after=run.to_dict(),
                      changed_only=True)  # fmt: skip
    return await _run_out(db, ctx, run)


async def mark_paid(db: AsyncSession, ctx: TenantContext, run_id: uuid.UUID, body: MarkPaidIn) -> PayrollRunOut:
    run = await _run(db, ctx, run_id, for_update=True)
    if run.status != LOCKED:
        raise InvalidStateError("Only locked payroll runs can be marked paid")
    if body.payment_date < run.pay_period_month:
        raise ValidationFailedError("Payment date is before the pay period", {"field": "payment_date"})
    await _assert_ledgers(db, ctx, [body.bank_ledger_id])
    settings = await _settings(db, ctx)
    before = run.to_dict()
    if run.total_net_pay > 0:
        E = accounts.SystemEntry  # noqa: N806
        run.payment_voucher_id = await accounts.post_system_voucher(
            db, ctx, base_type="PAYMENT", voucher_date=body.payment_date,
            entries=[E(settings.salary_payable_ledger_id, "DR", run.total_net_pay),
                     E(body.bank_ledger_id, "CR", run.total_net_pay)],
            narration=f"Salary disbursement for {exports.month_label(run.pay_period_month)}",
        )  # fmt: skip
    run.status = PAID
    await db.flush()
    await write_audit(db, ctx, MODULE, "POST", "payroll_run", run.id, before=before, after=run.to_dict(),
                      reason="mark-paid", changed_only=True)  # fmt: skip
    return await _run_out(db, ctx, run)


# ================================================================= files
@dataclass(frozen=True, slots=True)
class FileOut:
    content: bytes
    media_type: str
    filename: str


async def _slips(db: AsyncSession, ctx: TenantContext, run: PayrollRun) -> list[exports.SlipLine]:
    lines = await repo.run_lines(db, ctx.org_id, run.id)
    emps = await repo.employees_by_ids(db, ctx.org_id, [ln.employee_id for ln in lines])
    epf_cfg = (await _statutory(db, month_end(run.pay_period_month))).epf
    slips = [_slip(emps[ln.employee_id], ln, run.pay_period_month, epf_cfg) for ln in lines]
    return sorted(slips, key=lambda s: s.emp_code)


async def bank_file(db: AsyncSession, ctx: TenantContext, run_id: uuid.UUID, fmt: str | None) -> FileOut:
    run = await _run(db, ctx, run_id)
    if (fmt or "NEFT").upper() not in ("NEFT", "CSV", "NEFT_CSV"):
        raise ValidationFailedError("Unsupported bank file format", {"supported": ["NEFT"]})
    if run.status == DRAFT:
        raise InvalidStateError("Lock the payroll run before generating the bank file")
    slips = await _slips(db, ctx, run)
    incomplete = [s.emp_code for s in slips if s.net_pay > 0 and not (s.bank_account_no and s.bank_ifsc)]
    if incomplete:
        raise ValidationFailedError("Bank account or IFSC missing for some employees", {"emp_codes": incomplete})
    org = await _org(db, ctx)
    text = exports.bank_file_csv(slips, run.pay_period_month, org.legal_name)
    await write_audit(db, ctx, MODULE, "EXPORT", "payroll_run", run.id, reason="bank-file")
    return FileOut(text.encode(), "text/csv", f"salary-neft-{format_month(run.pay_period_month)}.csv")


async def statutory_file(db: AsyncSession, ctx: TenantContext, run_id: uuid.UUID, kind: str) -> FileOut:
    if kind not in STATUTORY_KINDS:
        raise NotFoundError("Unknown statutory file")
    run = await _run(db, ctx, run_id)
    slips = await _slips(db, ctx, run)
    month = format_month(run.pay_period_month)
    if kind == "epf-ecr":
        return FileOut(exports.epf_ecr(slips).encode(), "text/plain", f"epf-ecr-{month}.txt")
    if kind == "esic":
        return FileOut(exports.esic_csv(slips).encode(), "text/csv", f"esic-{month}.csv")
    settings = await _settings(db, ctx)
    return FileOut(exports.pt_csv(slips, settings.pt_state_code).encode(), "text/csv", f"pt-{month}.csv")


async def _stored_pdf(db: AsyncSession, ctx: TenantContext, document_id: uuid.UUID) -> bytes | None:
    try:
        doc = await documents.get_document(db, ctx, document_id)
        key = _field(doc, "storage_key", "file_storage_key")
        return await get_storage().get_bytes(key) if key else None
    except NotImplementedError:
        return None
    except NotFoundError:
        return None


async def payslip(db: AsyncSession, ctx: TenantContext, run_id: uuid.UUID, line_id: uuid.UUID) -> FileOut:
    run = await _run(db, ctx, run_id)
    ln = await repo.get_line(db, ctx.org_id, run.id, line_id)
    if ln is None:
        raise NotFoundError()
    e = await _employee(db, ctx, ln.employee_id)
    name = f"payslip-{e.emp_code}-{format_month(run.pay_period_month)}.pdf"
    data = await _stored_pdf(db, ctx, ln.payslip_doc_id) if ln.payslip_doc_id else None
    if data is None:
        epf_cfg = (await _statutory(db, month_end(run.pay_period_month))).epf
        data = exports.render_payslip(await _org(db, ctx), _slip(e, ln, run.pay_period_month, epf_cfg),
                                      run.pay_period_month)  # fmt: skip
    return FileOut(data, "application/pdf", name)
