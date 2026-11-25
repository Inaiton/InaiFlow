"""Superadmin services: dashboard, organizations (directory, lifecycle, plan, owner, impersonation), users,
system health, meta. Tenant-data mutations go through the owning modules' interfaces."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.email import get_email
from app.adapters.storage import get_storage
from app.adapters.taxgateway import get_tax_gateway
from app.core.config import get_settings
from app.core.context import AdminPrincipal
from app.core.errors import ForbiddenError, InvalidStateError, NotFoundError, ValidationFailedError
from app.core.pagination import Page, PageParams
from app.core.security import create_impersonation_token
from app.modules.identity import interface as identity
from app.modules.organization import interface as organization
from app.modules.platform.interface import MODULE_KEYS
from app.modules.superadmin import repository as repo
from app.modules.superadmin.audit import audit
from app.modules.superadmin.models import PlatformImpersonationSession
from app.modules.superadmin.schemas import (
    AdminDashboardOut,
    AdminMembershipOut,
    AdminOrgDetail,
    AdminOrgMemberOut,
    AdminOrgSummary,
    AdminUserDetail,
    AdminUserSummary,
    ImpersonateIn,
    ImpersonateOut,
    LifecycleIn,
    PlanChangeIn,
    SignupPoint,
    SystemHealthOut,
    TemplateTokenOut,
    TransferOwnerIn,
    UserActionIn,
)
from app.modules.superadmin.template_tokens import TEMPLATE_TOKENS

IMPERSONATION_TTL = timedelta(minutes=30)
QUOTA_INT_KEYS = ("max_internal_seats", "max_external_collaborators", "max_storage_gb")


def _now() -> datetime:
    return datetime.now(UTC)


async def _health(probe: Any) -> str:
    try:
        return str(await probe())
    except Exception:  # noqa: BLE001 - health must never raise
        return "error"


# ================================================================= dashboard
def _summary(r: Any) -> AdminOrgSummary:
    m = r._mapping
    return AdminOrgSummary(**{k: m[k] for k in AdminOrgSummary.model_fields})


async def dashboard(db: AsyncSession) -> AdminDashboardOut:
    c = await repo.dashboard_counts(db)
    return AdminDashboardOut(
        orgs_total=c.orgs_total, orgs_active=c.orgs_active, orgs_trial=c.orgs_trial, orgs_suspended=c.orgs_suspended,
        users_total=c.users_total, mrr_inr=Decimal(c.mrr_inr), active_runs=c.active_runs,
        vouchers_today=c.vouchers_today, storage_bytes=int(c.storage_bytes),
        irp_health=await _health(get_tax_gateway().health),
        signups_series=[SignupPoint(date=r.date, count=r.count) for r in await repo.signups_series(db)],
        recent_orgs=[_summary(r) for r in await repo.recent_orgs(db)],
    )  # fmt: skip


# ================================================================= organizations
async def list_orgs(db: AsyncSession, *, q: str | None, status: str | None, plan_code: str | None,
                    industry: str | None, page: PageParams) -> Page[AdminOrgSummary]:  # fmt: skip
    rows, total = await repo.org_page(db, q=q, status=status, plan_code=plan_code, industry=industry,
                                      limit=page.limit, offset=page.offset)  # fmt: skip
    return Page(items=[_summary(r) for r in rows], total=total, limit=page.limit, offset=page.offset)


async def org_detail(db: AsyncSession, org_id: uuid.UUID) -> AdminOrgDetail:
    r = await repo.org_row(db, org_id)
    if r is None:
        raise NotFoundError("Organization not found")
    s = await repo.org_stats(db, org_id)
    m = dict(r._mapping)
    return AdminOrgDetail(**{k: m[k] for k in AdminOrgSummary.model_fields}, owner_user_id=m["owner_user_id"],
                          owner_name=m["owner_name"], external_count=s.external_count,
                          storage_used_bytes=int(s.storage_used_bytes), quota_overrides=m["quota_overrides"] or {},
                          plan_id=m["plan_id"], contact_email=m["contact_email"], contact_phone=m["contact_phone"],
                          city=m["city"], voucher_count=s.voucher_count, run_count=s.run_count)  # fmt: skip


async def _state(db: AsyncSession, org_id: uuid.UUID) -> organization.OrgAdminState:
    state = await organization.get_org_admin_state(db, org_id)
    if state is None:
        raise NotFoundError("Organization not found")
    return state


async def lifecycle(db: AsyncSession, admin: AdminPrincipal, org_id: uuid.UUID, body: LifecycleIn) -> AdminOrgDetail:
    before = await _state(db, org_id)
    cur = before.org_status
    if body.action == "ARCHIVE":
        if admin.role != "SUPERADMIN":
            raise ForbiddenError("Only a SUPERADMIN can archive an organization")
        if cur == "ARCHIVED":
            raise InvalidStateError("The organization is already archived")
        after = await organization.set_org_status(db, org_id, "ARCHIVED")
    elif body.action == "SUSPEND":
        if cur not in ("ACTIVE", "TRIAL"):
            raise InvalidStateError(f"Cannot suspend an organization in status {cur}")
        after = await organization.set_org_status(db, org_id, "SUSPENDED")
    elif body.action == "ACTIVATE":
        if cur == "ACTIVE":
            raise InvalidStateError("The organization is already active")
        after = await organization.set_org_status(db, org_id, "ACTIVE")
    else:  # EXTEND_TRIAL
        if not body.trial_days:
            raise ValidationFailedError("trial_days is required to extend a trial", {"trial_days": ["required"]})
        if cur not in ("TRIAL", "SUSPENDED"):
            raise InvalidStateError(f"Cannot extend the trial of an organization in status {cur}")
        start = max(_now(), before.trial_ends_at or _now())
        after = await organization.set_org_status(db, org_id, "TRIAL",
                                                  trial_ends_at=start + timedelta(days=body.trial_days))  # fmt: skip
    if after.org_status in ("SUSPENDED", "ARCHIVED"):
        await repo.end_impersonations(db, org_id=org_id)
    await audit(db, admin, f"ORG_{body.action}", "ORGANIZATION", org_id, before=before.as_dict(),
                after={**after.as_dict(), "trial_days": body.trial_days}, reason=body.reason)  # fmt: skip
    return await org_detail(db, org_id)


def _validated_quota(q: dict[str, Any]) -> dict[str, Any]:
    allowed = {*QUOTA_INT_KEYS, "enabled_modules"}
    unknown = sorted(set(q) - allowed)
    if unknown:
        raise ValidationFailedError(f"Unknown quota override: {unknown[0]}", {"allowed": sorted(allowed)})
    out: dict[str, Any] = {}
    for k in QUOTA_INT_KEYS:
        if k in q:
            v = q[k]
            if isinstance(v, bool) or not isinstance(v, int) or v < 0:
                raise ValidationFailedError(f"{k} must be a non-negative integer")
            out[k] = v
    if "enabled_modules" in q:
        mods = q["enabled_modules"]
        if not isinstance(mods, dict) or any(k not in MODULE_KEYS or not isinstance(v, bool) for k, v in mods.items()):
            raise ValidationFailedError("enabled_modules must map module keys to booleans",
                                        {"modules": list(MODULE_KEYS)})  # fmt: skip
        out["enabled_modules"] = mods
    return out


async def change_plan(db: AsyncSession, admin: AdminPrincipal, org_id: uuid.UUID, body: PlanChangeIn) -> AdminOrgDetail:
    before = await _state(db, org_id)
    plan = await repo.get_plan(db, body.plan_id)
    if plan is None:
        raise NotFoundError("Plan not found")
    if not plan.is_active and plan.id != before.plan_id:
        raise ValidationFailedError("This plan is not active")
    quota = _validated_quota(body.quota_overrides) if body.quota_overrides is not None else None
    after = await organization.set_org_plan(db, org_id, body.plan_id, quota)
    await audit(db, admin, "ORG_PLAN_CHANGE", "ORGANIZATION", org_id, before=before.as_dict(),
                after={**after.as_dict(), "plan_code": plan.plan_code}, reason=body.reason)  # fmt: skip
    return await org_detail(db, org_id)


async def transfer_owner(db: AsyncSession, admin: AdminPrincipal, org_id: uuid.UUID,
                         body: TransferOwnerIn) -> AdminOrgDetail:  # fmt: skip
    before = await _state(db, org_id)
    after = await organization.transfer_owner_by_platform(db, org_id, body.new_owner_user_id)
    await audit(db, admin, "ORG_TRANSFER_OWNER", "ORGANIZATION", org_id,
                before={"owner_user_id": before.owner_user_id}, after={"owner_user_id": after.owner_user_id},
                reason=body.reason)  # fmt: skip
    return await org_detail(db, org_id)


async def org_members(db: AsyncSession, org_id: uuid.UUID) -> list[AdminOrgMemberOut]:
    await _state(db, org_id)
    members = await organization.org_memberships(db, org_id)
    users = await identity.user_briefs(db, [m.user_id for m in members])
    return [AdminOrgMemberOut(user_id=m.user_id, full_name=users[m.user_id].full_name, email=users[m.user_id].email,
                              role_code=m.role_code, status=m.status)
            for m in members if m.user_id in users]  # fmt: skip


async def impersonate(
    db: AsyncSession, admin: AdminPrincipal, org_id: uuid.UUID, body: ImpersonateIn
) -> ImpersonateOut:
    state = await _state(db, org_id)
    if state.org_status == "ARCHIVED":
        raise InvalidStateError("Archived organizations cannot be impersonated")
    expires = _now() + IMPERSONATION_TTL
    session = PlatformImpersonationSession(admin_id=admin.admin_id, org_id=org_id, mode=body.mode,
                                           ticket_reference=body.ticket_reference, reason=body.reason,
                                           expires_at=expires)  # fmt: skip
    await repo.add(db, session)
    token = create_impersonation_token(admin_id=admin.admin_id, session_id=session.id, org_id=org_id, mode=body.mode,
                                       expires_at=expires)  # fmt: skip
    launch = f"{get_settings().PUBLIC_USER_WEB_URL.rstrip('/')}/impersonate#token={token}&org_id={org_id}"
    await audit(db, admin, "IMPERSONATION_START", "ORGANIZATION", org_id,
                after={"session_id": session.id, "mode": body.mode, "ticket_reference": body.ticket_reference,
                       "expires_at": expires}, reason=body.reason)  # fmt: skip
    return ImpersonateOut(session_id=session.id, token=token, expires_at=expires, launch_url=launch)


# ================================================================= users
def _user_summary(r: Any) -> AdminUserSummary:
    m = r._mapping
    return AdminUserSummary(**{k: m[k] for k in AdminUserSummary.model_fields})


async def list_users(db: AsyncSession, *, q: str | None, suspended: bool | None,
                     page: PageParams) -> Page[AdminUserSummary]:  # fmt: skip
    rows, total = await repo.user_page(db, q=q, suspended=suspended, limit=page.limit, offset=page.offset)
    return Page(items=[_user_summary(r) for r in rows], total=total, limit=page.limit, offset=page.offset)


async def user_detail(db: AsyncSession, user_id: uuid.UUID) -> AdminUserDetail:
    r = await repo.user_row(db, user_id)
    if r is None:
        raise NotFoundError("User not found")
    memberships = [AdminMembershipOut(org_id=m.org_id, org_name=m.org_name, role_code=m.role_code, status=m.status,
                                      access_expires_at=m.access_expires_at)
                   for m in await organization.memberships_for_user(db, user_id)]  # fmt: skip
    return AdminUserDetail(**_user_summary(r).model_dump(), mobile=r.mobile, professional_reg_no=r.professional_reg_no,
                           memberships=memberships, active_sessions=await identity.active_session_count(db, user_id))  # fmt: skip


async def user_action(
    db: AsyncSession, admin: AdminPrincipal, user_id: uuid.UUID, body: UserActionIn
) -> AdminUserDetail:
    before = await identity.user_brief(db, user_id)
    if before is None:
        raise NotFoundError("User not found")
    snapshot = {"is_suspended": before.is_suspended, "mfa_enabled": before.mfa_enabled,
                "is_email_verified": before.is_email_verified}  # fmt: skip
    extra: dict[str, Any] = {}
    if body.action == "SUSPEND":
        if before.is_suspended:
            raise InvalidStateError("The user is already suspended")
        await identity.set_user_suspended(db, user_id, True)
    elif body.action == "UNSUSPEND":
        if not before.is_suspended:
            raise InvalidStateError("The user is not suspended")
        await identity.set_user_suspended(db, user_id, False)
    elif body.action == "RESET_MFA":
        if not before.mfa_enabled:
            raise InvalidStateError("Two-factor authentication is not enabled for this user")
        await identity.reset_user_mfa(db, user_id)
    elif body.action == "VERIFY_EMAIL":
        if before.is_email_verified:
            raise InvalidStateError("The email address is already verified")
        await identity.mark_email_verified(db, user_id)
    else:
        extra["sessions_revoked"] = await identity.revoke_all_sessions(db, user_id, "ADMIN_REVOKED")
    after = await identity.user_brief(db, user_id)
    await audit(db, admin, f"USER_{body.action}", "USER", user_id, before=snapshot,
                after={"is_suspended": after.is_suspended, "mfa_enabled": after.mfa_enabled,
                       "is_email_verified": after.is_email_verified, **extra} if after else extra,
                reason=body.reason)  # fmt: skip
    return await user_detail(db, user_id)


# ================================================================= system & meta
async def system_health(db: AsyncSession) -> SystemHealthOut:
    try:
        await db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:  # noqa: BLE001
        db_status = "error"
    s = get_settings()
    return SystemHealthOut(db=db_status, storage=await _health(get_storage().health),
                           email=await _health(get_email().health), tax_gateway=await _health(get_tax_gateway().health),
                           version=s.APP_VERSION, environment=s.APP_ENV)  # fmt: skip


def template_tokens() -> list[TemplateTokenOut]:
    """Prefer the documents module's catalogue when S4 exposes one; else the shared catalogue owned here."""
    from app.modules.documents import interface as documents

    provider = getattr(documents, "template_tokens", None)
    if callable(provider):
        try:
            return [TemplateTokenOut(token=t.token, label=t.label, group=t.group, sample=t.sample) for t in provider()]
        except Exception:  # noqa: BLE001 - fall back to the shared catalogue
            logging.getLogger("inaiflow.superadmin").exception("documents.template_tokens failed")
    return [TemplateTokenOut(**t._asdict()) for t in TEMPLATE_TOKENS]
