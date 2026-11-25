"""Public API of the organization module."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import TenantContext
from app.core.errors import NotFoundError
from app.modules.organization import repository as _repo

if TYPE_CHECKING:
    from app.modules.organization.schemas import InvitationIn, InvitationOut


@dataclass(frozen=True, slots=True)
class OrgBrief:
    id: uuid.UUID
    legal_name: str
    mailing_name: str | None
    workspace_slug: str
    state_code: str
    state_name: str
    gstin: str | None
    pan: str | None
    tan: str | None
    gst_reg_type: str
    address_lines: list[str]
    contact_email: str
    contact_phone: str
    base_currency_code: str
    base_currency_symbol: str
    fy_begins_from: date
    books_beginning_from: date
    industry_type: str
    logo_storage_key: str | None
    stamp_storage_key: str | None
    accounts_settings: dict[str, Any]
    security_settings: dict[str, Any]
    org_status: str
    owner_user_id: uuid.UUID


async def get_org_brief(db: AsyncSession, org_id: uuid.UUID) -> OrgBrief | None:
    o = await _repo.get_org(db, org_id)
    if o is None:
        return None
    lines = [x for x in (o.address_line1, o.address_line2, f"{o.city} - {o.pincode}", o.state_name) if x]
    return OrgBrief(o.id, o.legal_name, o.mailing_name, o.workspace_slug, o.state_code, o.state_name, o.gstin,
                    o.pan, o.tan, o.gst_reg_type, lines, o.contact_email, o.contact_phone, o.base_currency_code,
                    o.base_currency_symbol, o.fy_begins_from, o.books_beginning_from, o.industry_type,
                    o.logo_storage_key, o.stamp_storage_key, dict(o.accounts_settings or {}),
                    dict(o.security_settings or {}), o.org_status, o.owner_user_id)  # fmt: skip


async def update_accounts_settings(db: AsyncSession, ctx: TenantContext, settings: dict[str, Any]) -> dict[str, Any]:
    """Replace ``organizations.accounts_settings`` (books_locked_until, invoice settings...). Accounts owns
    the content; the column lives here."""
    org = await _repo.get_org(db, ctx.org_id)
    if org is None:
        raise NotFoundError()
    org.accounts_settings = dict(settings)
    await db.flush()
    return dict(org.accounts_settings)


async def member_counts_by_role(db: AsyncSession, org_id: uuid.UUID) -> dict[uuid.UUID, int]:
    return await _repo.member_counts_by_role(db, org_id)


async def is_member(db: AsyncSession, org_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    m = await _repo.membership_for_user(db, org_id, user_id)
    return m is not None and m.status in ("ACTIVE", "SUSPENDED")


async def active_member_user_ids(db: AsyncSession, org_id: uuid.UUID) -> list[uuid.UUID]:
    return [m.user_id for m in await _repo.list_members(db, org_id, "ACTIVE")]


async def invite_member(db: AsyncSession, ctx: TenantContext, body: InvitationIn) -> InvitationOut:
    """Create a push invitation (used by operations' auditor invites). Same rules as POST /organization/invitations."""
    from app.modules.organization import service

    return await service.create_invitation(db, ctx, body)


# ---- cron helpers (platform session)
async def expire_invitations(db: AsyncSession) -> int:
    return await _repo.expire_invitations(db)


async def expire_memberships(db: AsyncSession) -> int:
    return await _repo.expire_memberships(db)


async def list_active_org_ids(db: AsyncSession) -> list[uuid.UUID]:
    return await _repo.active_org_ids(db)


async def release_role(db: AsyncSession, org_id: uuid.UUID, role_id: uuid.UUID) -> None:
    await _repo.release_role(db, org_id, role_id)


# ---------------------------------------------------------------- platform-admin operations (added by S5)
# Called by the superadmin module on the platform session (connection user, owner RLS policy).
@dataclass(frozen=True, slots=True)
class MembershipBrief:
    org_id: uuid.UUID
    org_name: str
    user_id: uuid.UUID
    role_id: uuid.UUID
    role_code: str
    is_external: bool
    status: str
    access_expires_at: Any


@dataclass(frozen=True, slots=True)
class OrgAdminState:
    """The fields platform admins change (lifecycle, plan, owner) — used for before/after audit."""

    id: uuid.UUID
    org_status: str
    trial_ends_at: Any
    plan_id: uuid.UUID | None
    quota_overrides: dict[str, Any]
    owner_user_id: uuid.UUID

    def as_dict(self) -> dict[str, Any]:
        return {"org_status": self.org_status, "trial_ends_at": self.trial_ends_at, "plan_id": self.plan_id,
                "quota_overrides": dict(self.quota_overrides), "owner_user_id": self.owner_user_id}  # fmt: skip


def _state(o: Any) -> OrgAdminState:
    return OrgAdminState(o.id, o.org_status, o.trial_ends_at, o.plan_id, dict(o.quota_overrides or {}), o.owner_user_id)


async def _memberships(db: AsyncSession, rows: list[Any]) -> list[MembershipBrief]:
    from app.modules.rbac import interface as rbac

    roles = await rbac.roles_by_ids(db, list({m.role_id for m, _ in rows}))
    out = []
    for m, org in rows:
        role = roles.get(m.role_id)
        out.append(MembershipBrief(m.org_id, org.legal_name, m.user_id, m.role_id, getattr(role, "role_code", ""),
                                   bool(getattr(role, "is_external_collaborator", False)), m.status,
                                   m.access_expires_at))  # fmt: skip
    return out


async def memberships_for_user(db: AsyncSession, user_id: uuid.UUID) -> list[MembershipBrief]:
    """Every non-revoked membership of a user across orgs (platform session)."""
    return await _memberships(db, await _repo.my_orgs(db, user_id))


async def org_memberships(db: AsyncSession, org_id: uuid.UUID) -> list[MembershipBrief]:
    """Non-revoked memberships of one org (platform session)."""
    org = await _repo.get_org(db, org_id)
    if org is None:
        return []
    return await _memberships(db, [(m, org) for m in await _repo.list_members(db, org_id, None)])


async def get_org_admin_state(db: AsyncSession, org_id: uuid.UUID) -> OrgAdminState | None:
    o = await _repo.get_org(db, org_id)
    return _state(o) if o else None


_UNSET: Any = object()


async def set_org_status(
    db: AsyncSession, org_id: uuid.UUID, status: str, *, trial_ends_at: Any = _UNSET
) -> OrgAdminState:  # fmt: skip
    """Lifecycle change (ACTIVE | TRIAL | SUSPENDED | ARCHIVED); the caller validates transitions."""
    from datetime import UTC, datetime

    if status not in ("ACTIVE", "TRIAL", "SUSPENDED", "ARCHIVED"):
        raise ValueError(f"unknown org status {status!r}")
    o = await _repo.get_org(db, org_id)
    if o is None:
        raise NotFoundError()
    o.org_status, o.updated_at = status, datetime.now(UTC)
    if trial_ends_at is not _UNSET:
        o.trial_ends_at = trial_ends_at
    await db.flush()
    return _state(o)


async def set_org_plan(
    db: AsyncSession, org_id: uuid.UUID, plan_id: uuid.UUID, quota_overrides: dict[str, Any] | None = None
) -> OrgAdminState:  # fmt: skip
    """Assign a subscription plan; ``quota_overrides`` (when given) replaces the org's overrides."""
    from datetime import UTC, datetime

    o = await _repo.get_org(db, org_id)
    if o is None:
        raise NotFoundError()
    o.plan_id, o.updated_at = plan_id, datetime.now(UTC)
    if quota_overrides is not None:
        o.quota_overrides = dict(quota_overrides)
    await db.flush()
    return _state(o)


async def transfer_owner_by_platform(
    db: AsyncSession, org_id: uuid.UUID, new_owner_user_id: uuid.UUID
) -> OrgAdminState:
    """Platform-admin owner transfer: target must be an ACTIVE internal member; the old owner becomes ADMIN."""
    from datetime import UTC, datetime

    from app.core.errors import ValidationFailedError
    from app.modules.rbac import interface as rbac

    o = await _repo.get_org(db, org_id)
    if o is None:
        raise NotFoundError()
    if new_owner_user_id == o.owner_user_id:
        raise ValidationFailedError("This user already owns the organization")
    target = await _repo.membership_for_user(db, org_id, new_owner_user_id)
    if target is None or target.status != "ACTIVE":
        raise ValidationFailedError("The new owner must be an active member of the organization")
    target_role = await rbac.get_role(db, org_id, target.role_id)
    if target_role is None or target_role.is_external_collaborator:
        raise ValidationFailedError("External collaborators cannot own the organization")
    owner_role = await rbac.get_role_by_code(db, org_id, "ORG_OWNER")
    admin_role = await rbac.get_role_by_code(db, org_id, "ADMIN")
    if owner_role is None or admin_role is None:
        raise NotFoundError()
    current = await _repo.membership_for_user(db, org_id, o.owner_user_id)
    target.role_id = owner_role.id
    if current is not None:
        current.role_id = admin_role.id
    o.owner_user_id, o.updated_at = new_owner_user_id, datetime.now(UTC)
    await db.flush()
    return _state(o)
