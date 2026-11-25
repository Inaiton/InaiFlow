"""Plans, subscription invoices, platform audit log, admin accounts."""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import AdminPrincipal
from app.core.errors import AlreadyExistsError, InvalidStateError, NotFoundError, ValidationFailedError
from app.core.pagination import Page, PageParams
from app.core.security import hash_password
from app.modules.platform.interface import MODULE_KEYS
from app.modules.superadmin import repository as repo
from app.modules.superadmin.audit import audit
from app.modules.superadmin.models import PlatformAdmin, PlatformSubscriptionInvoice
from app.modules.superadmin.schemas import (
    AdminAccountCreatedOut,
    AdminAccountIn,
    AdminAccountOut,
    AdminAccountUpdateIn,
    InvoiceStatusIn,
    PlanIn,
    PlanOut,
    PlanUpdateIn,
    PlatformAuditOut,
    SubscriptionInvoiceIn,
    SubscriptionInvoiceOut,
)

#: Allowed invoice status transitions (VOID is terminal).
INVOICE_TRANSITIONS = {("DUE", "PAID"), ("DUE", "VOID"), ("PAID", "VOID")}


def _now() -> datetime:
    return datetime.now(UTC)


# ================================================================= plans
def _plan_out(r: Any) -> PlanOut:
    m = dict(r._mapping)
    m["enabled_modules"] = {k: bool(v) for k, v in (m["enabled_modules"] or {}).items()}
    return PlanOut(**m)


def _check_plan_values(v: dict[str, Any]) -> None:
    mods = v.get("enabled_modules")
    if mods is not None:
        unknown = sorted(set(mods) - set(MODULE_KEYS))
        if unknown:
            raise ValidationFailedError(f"Unknown module key: {unknown[0]}", {"modules": list(MODULE_KEYS)})
    for k in ("monthly_price_inr", "annual_price_inr"):
        if v.get(k) is not None and Decimal(v[k]) < 0:
            raise ValidationFailedError(f"{k} must not be negative")


async def list_plans(db: AsyncSession) -> list[PlanOut]:
    return [_plan_out(r) for r in await repo.list_plans(db)]


async def _plan(db: AsyncSession, plan_id: uuid.UUID) -> PlanOut:
    r = await repo.get_plan(db, plan_id)
    if r is None:
        raise NotFoundError("Plan not found")
    return _plan_out(r)


async def create_plan(db: AsyncSession, admin: AdminPrincipal, body: PlanIn) -> PlanOut:
    values = body.model_dump(exclude={"reason"})
    values["is_active"] = True if body.is_active is None else body.is_active
    _check_plan_values(values)
    if await repo.plan_code_taken(db, body.plan_code):
        raise AlreadyExistsError("A plan with this code already exists")
    plan_id = await repo.insert_plan(db, values)
    out = await _plan(db, plan_id)
    await audit(db, admin, "PLAN_CREATE", "PLAN", plan_id, after=out.model_dump(mode="json"), reason=body.reason)
    return out


async def update_plan(db: AsyncSession, admin: AdminPrincipal, plan_id: uuid.UUID, body: PlanUpdateIn) -> PlanOut:
    before = await _plan(db, plan_id)
    values = body.model_dump(exclude={"reason"}, exclude_none=True)
    _check_plan_values(values)
    await repo.update_plan(db, plan_id, values)
    after = await _plan(db, plan_id)
    await audit(db, admin, "PLAN_UPDATE", "PLAN", plan_id, before=before.model_dump(mode="json"),
                after=after.model_dump(mode="json"), reason=body.reason)  # fmt: skip
    return after


# ================================================================= invoices
def _invoice_out(inv: PlatformSubscriptionInvoice | Any, org_name: str) -> SubscriptionInvoiceOut:
    return SubscriptionInvoiceOut(id=inv.id, org_id=inv.org_id, org_name=org_name, invoice_number=inv.invoice_number,
                                  period_start=inv.period_start, period_end=inv.period_end, amount_inr=inv.amount_inr,
                                  status=inv.status, paid_at=inv.paid_at, created_at=inv.created_at)  # fmt: skip


async def list_invoices(db: AsyncSession, *, org_id: uuid.UUID | None, status: str | None,
                        page: PageParams) -> Page[SubscriptionInvoiceOut]:  # fmt: skip
    rows, total = await repo.invoice_page(db, org_id=org_id, status=status, limit=page.limit, offset=page.offset)
    return Page(items=[SubscriptionInvoiceOut(**dict(r._mapping)) for r in rows], total=total, limit=page.limit,
                offset=page.offset)  # fmt: skip


async def create_invoice(
    db: AsyncSession, admin: AdminPrincipal, body: SubscriptionInvoiceIn
) -> SubscriptionInvoiceOut:
    name = await repo.org_name(db, body.org_id)
    if name is None:
        raise NotFoundError("Organization not found")
    if body.period_end < body.period_start:
        raise ValidationFailedError("period_end must be on or after period_start")
    if body.amount_inr <= 0:
        raise ValidationFailedError("amount_inr must be positive")
    number = await repo.next_invoice_number(db, f"INV-{_now():%Y%m}")
    inv = PlatformSubscriptionInvoice(org_id=body.org_id, invoice_number=number, period_start=body.period_start,
                                      period_end=body.period_end, amount_inr=body.amount_inr, status="DUE")  # fmt: skip
    await repo.add(db, inv)
    await db.refresh(inv)
    out = _invoice_out(inv, name)
    await audit(db, admin, "INVOICE_CREATE", "INVOICE", inv.id, after=out.model_dump(mode="json"), reason=body.reason)
    return out


async def set_invoice_status(db: AsyncSession, admin: AdminPrincipal, invoice_id: uuid.UUID,
                             body: InvoiceStatusIn) -> SubscriptionInvoiceOut:  # fmt: skip
    inv = await repo.invoice_by_id(db, invoice_id, lock=True)
    if inv is None:
        raise NotFoundError("Invoice not found")
    before = {"status": inv.status, "paid_at": inv.paid_at}
    if (inv.status, body.status) not in INVOICE_TRANSITIONS:
        raise InvalidStateError(f"Cannot change an invoice from {inv.status} to {body.status}")
    inv.status = body.status
    if body.status == "PAID":
        inv.paid_at = _now()
    await db.flush()
    await audit(db, admin, f"INVOICE_{body.status}", "INVOICE", inv.id, before=before,
                after={"status": inv.status, "paid_at": inv.paid_at}, reason=body.reason)  # fmt: skip
    return _invoice_out(inv, await repo.org_name(db, inv.org_id) or "")


# ================================================================= platform audit
async def audit_logs(db: AsyncSession, page: PageParams, **filters: Any) -> Page[PlatformAuditOut]:
    rows, total = await repo.audit_page(db, limit=page.limit, offset=page.offset, **filters)
    return Page(items=[PlatformAuditOut(**dict(r._mapping)) for r in rows], total=total, limit=page.limit,
                offset=page.offset)  # fmt: skip


# ================================================================= admin accounts
def _admin_out(a: PlatformAdmin) -> AdminAccountOut:
    return AdminAccountOut(id=a.id, email=a.email, full_name=a.full_name, role=a.role, is_active=a.is_active,
                           mfa_enabled=a.mfa_enabled, last_login_at=a.last_login_at, created_at=a.created_at)  # fmt: skip


def _snapshot(a: PlatformAdmin) -> dict[str, Any]:
    return {"role": a.role, "is_active": a.is_active}


async def list_admins(db: AsyncSession) -> list[AdminAccountOut]:
    return [_admin_out(a) for a in await repo.list_admins(db)]


async def create_admin(db: AsyncSession, admin: AdminPrincipal, body: AdminAccountIn) -> AdminAccountCreatedOut:
    if await repo.admin_by_email(db, body.email) is not None:
        raise AlreadyExistsError("An admin with this email already exists")
    password = secrets.token_urlsafe(18)  # shown once; must be changed (with MFA enrollment) at first sign-in
    a = PlatformAdmin(email=body.email, full_name=body.full_name.strip(), role=body.role,
                      password_hash=await hash_password(password), must_change_password=True, mfa_enabled=False,
                      is_active=True)  # fmt: skip
    await repo.add(db, a)
    await db.refresh(a)
    await audit(db, admin, "ADMIN_CREATE", "PLATFORM_ADMIN", a.id,
                after={"email": a.email, "full_name": a.full_name, **_snapshot(a)})  # fmt: skip
    return AdminAccountCreatedOut(admin=_admin_out(a), temporary_password=password)


async def update_admin(db: AsyncSession, admin: AdminPrincipal, admin_id: uuid.UUID,
                       body: AdminAccountUpdateIn) -> AdminAccountOut:  # fmt: skip
    await repo.lock_admins(db)
    a = await repo.admin_by_id(db, admin_id, lock=True)
    if a is None:
        raise NotFoundError("Admin not found")
    before = _snapshot(a)
    new_role = body.role or a.role
    new_active = a.is_active if body.is_active is None else body.is_active
    if a.id == admin.admin_id and (new_role != a.role or not new_active):
        raise InvalidStateError("You cannot change your own role or deactivate yourself")
    loses_super = a.role == "SUPERADMIN" and a.is_active and (new_role != "SUPERADMIN" or not new_active)
    if loses_super and await repo.count_active_superadmins(db) <= 1:
        raise InvalidStateError("The last active SUPERADMIN cannot be demoted or deactivated")
    a.role, a.is_active = new_role, new_active
    if not new_active:  # role changes apply immediately (the guard reads the role per request)
        await repo.revoke_admin_sessions(db, a.id, "DEACTIVATED")
        await repo.end_impersonations(db, admin_id=a.id)
    await db.flush()
    await audit(
        db, admin, "ADMIN_UPDATE", "PLATFORM_ADMIN", a.id, before=before, after=_snapshot(a), reason=body.reason
    )
    return _admin_out(a)
