"""Organization services: creation + seeding orchestration, personal-space flows (my orgs, invitations,
join requests) and tenant administration (profile, branches, members, invitations, security, audit, billing)."""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.email import EmailMessage, get_email
from app.adapters.storage import IMAGE_MIME_ALLOWLIST, get_storage, sanitize_name, validate_upload
from app.core.audit import write_audit
from app.core.config import get_settings
from app.core.context import Principal, TenantContext
from app.core.db import set_tenant_scope
from app.core.errors import (
    AlreadyExistsError,
    ConflictError,
    ForbiddenError,
    InvalidCredentialsError,
    InvalidStateError,
    NotFoundError,
    QuotaExceededError,
    SystemRecordError,
    ValidationFailedError,
)
from app.core.fy import fy_for_date
from app.core.pagination import Page
from app.core.permissions import ALL_PERMISSION_KEYS
from app.core.schemas import AuditLogOut, UploadTicket
from app.modules.accounts import interface as accounts
from app.modules.documents import interface as documents
from app.modules.identity import interface as identity
from app.modules.operations import interface as operations
from app.modules.organization import repository as repo
from app.modules.organization.models import Organization, OrgBranch, OrgInvitationOrRequest, OrgMembership
from app.modules.organization.schemas import (
    BillingOut,
    BranchIn,
    BranchOut,
    FyOut,
    ImpersonationInfo,
    InvitationForMeOut,
    InvitationIn,
    InvitationOut,
    JoinDecisionIn,
    JoinRequestIn,
    JoinRequestOut,
    MemberOut,
    MemberUpdateIn,
    MyJoinRequestOut,
    MyOrgOut,
    OrgContextOut,
    OrgCreateIn,
    OrgFileUploadIn,
    OrgOut,
    OrgUpdateIn,
    SecuritySettings,
    TransferOwnershipIn,
)
from app.modules.payroll import interface as payroll
from app.modules.platform import interface as platform
from app.modules.rbac import interface as rbac
from app.seeds.plans import DEFAULT_PLAN_CODE, TRIAL_DAYS
from app.seeds.states import STATE_NAMES

INVITE_TTL = timedelta(days=7)
RESERVED_SLUGS = {"admin", "api", "app", "www", "login", "signup", "me", "organizations", "superadmin", "auth",
                  "static", "settings", "help", "support", "billing"}  # fmt: skip
DEFAULT_SECURITY = {"enforce_2fa_external": True, "enforce_2fa_all": False, "session_timeout_mins": 480,
                    "voucher_approval_threshold": None, "require_reviewer_for_iso_docs": True}  # fmt: skip


def _now() -> datetime:
    return datetime.now(UTC)


async def _url(key: str | None, fallback: str | None = None) -> str | None:
    if not key:
        return fallback
    return (await get_storage().create_download_url(key)).url


# ================================================================= creation
async def check_slug(db: AsyncSession, slug: str) -> bool:
    import re

    if not re.fullmatch(r"[a-z0-9-]{3,50}", slug) or slug in RESERVED_SLUGS:
        return False
    return not await repo.slug_taken(db, slug)


async def _new_join_code(db: AsyncSession) -> str:
    for digits in (4, 4, 4, 4, 5, 5, 5, 6, 6, 6):
        code = f"ORG-{secrets.randbelow(10**digits):0{digits}d}"
        if len(code) - 4 == digits and not code.startswith("ORG-0") and not await repo.join_code_taken(db, code):
            return code
    raise ConflictError("Could not allocate a workspace code, please retry")


def _owner_ctx(org_id: uuid.UUID, principal: Principal, membership_id: uuid.UUID | None,
               role_id: uuid.UUID | None) -> TenantContext:  # fmt: skip
    return TenantContext(org_id=org_id, user_id=principal.user_id, membership_id=membership_id,
                         role_code="ORG_OWNER", role_id=role_id, is_external=False, is_owner=True,
                         permissions=dict.fromkeys(ALL_PERMISSION_KEYS, "FULL"), mfa=principal.mfa,
                         ip=principal.ip, user_agent=principal.user_agent, actor_type="USER",
                         actor_id=principal.user_id, role_name="Organization Owner")  # fmt: skip


async def create_organization(db: AsyncSession, principal: Principal, body: OrgCreateIn) -> MyOrgOut:
    """One transaction: org row, roles, owner membership, accounts/documents/operations/payroll seeds, audit."""
    if not await check_slug(db, body.workspace_slug):
        raise AlreadyExistsError("This workspace URL is not available", {"field": "workspace_slug"})
    state_name = STATE_NAMES.get(body.state_code)
    if state_name is None:
        raise ValidationFailedError("Unknown state code", {"field": "state_code"})
    if body.books_beginning_from < body.fy_begins_from:
        raise ValidationFailedError("Books cannot begin before the financial year starts")
    if body.gstin and body.gstin[:2] != body.state_code:
        raise ValidationFailedError("GSTIN does not match the state code", {"field": "gstin"})
    plan = await platform.get_plan_by_code(db, DEFAULT_PLAN_CODE)
    join_code = await _new_join_code(db)
    org_id = uuid.uuid4()

    await set_tenant_scope(db, org_id, principal.user_id)  # everything below runs under RLS
    data = body.model_dump()
    org = Organization(id=org_id, public_join_code=join_code, state_name=state_name,
                       owner_user_id=principal.user_id, plan_id=plan.id if plan else None, org_status="TRIAL",
                       trial_ends_at=_now() + timedelta(days=TRIAL_DAYS), security_settings=dict(DEFAULT_SECURITY),
                       quota_overrides={}, accounts_settings={}, **data)  # fmt: skip
    await repo.add(db, org)
    ctx = _owner_ctx(org_id, principal, None, None)
    roles = await rbac.seed_org_roles(db, ctx)
    membership = OrgMembership(org_id=org_id, user_id=principal.user_id, role_id=roles["ORG_OWNER"], status="ACTIVE")
    await repo.add(db, membership)
    ctx = _owner_ctx(org_id, principal, membership.id, roles["ORG_OWNER"])
    await accounts.seed_org_accounts(db, ctx, body.industry_type)
    await documents.seed_org_documents(db, ctx)
    await operations.seed_org_operations(db, ctx)
    await payroll.seed_org_payroll(db, ctx)
    await write_audit(db, ctx, "ORGANIZATION", "CREATE", "organization", org_id, after=org.to_dict())
    return await _my_org(db, principal.user_id, org_id)


# ================================================================= personal space
async def _my_org_rows_out(db: AsyncSession, rows: list[Any]) -> list[MyOrgOut]:
    roles = await rbac.roles_by_ids(db, [m.role_id for m, _ in rows])
    out = []
    for m, o in rows:
        role = roles.get(m.role_id)
        expired = m.status == "EXPIRED" or (m.access_expires_at is not None and m.access_expires_at <= _now())
        out.append(MyOrgOut(org_id=o.id, legal_name=o.legal_name, mailing_name=o.mailing_name,
                            workspace_slug=o.workspace_slug, public_join_code=o.public_join_code,
                            logo_url=await _url(o.logo_storage_key, o.logo_url), role_id=m.role_id,
                            role_code=role.role_code if role else "", role_name=role.role_name if role else "",
                            is_external=bool(role and role.is_external_collaborator),
                            membership_status="EXPIRED" if expired else m.status,
                            access_expires_at=m.access_expires_at, org_status=o.org_status))  # fmt: skip
    return out


async def _my_org(db: AsyncSession, user_id: uuid.UUID, org_id: uuid.UUID) -> MyOrgOut:
    out = await _my_org_rows_out(db, await repo.my_orgs(db, user_id, org_id))
    if not out:
        raise NotFoundError()
    return out[0]


async def my_organizations(db: AsyncSession, principal: Principal) -> list[MyOrgOut]:
    return await _my_org_rows_out(db, await repo.my_orgs(db, principal.user_id))


async def my_invitations(db: AsyncSession, principal: Principal) -> list[InvitationForMeOut]:
    rows = await repo.invitations_for_me(db, principal.user_id, principal.email.lower())
    roles = await rbac.roles_by_ids(db, [inv.proposed_role_id for inv, _ in rows])
    users = await identity.user_briefs(db, [inv.created_by for inv, _ in rows if inv.created_by])
    return [
        InvitationForMeOut(
            id=inv.id,
            org_id=inv.org_id,
            org_name=org_name,
            role_name=getattr(roles.get(inv.proposed_role_id), "role_name", ""),
            invited_by_name=getattr(users.get(inv.created_by), "full_name", None),
            access_expires_at=inv.access_expires_at,
            expires_at=inv.expires_at,
            created_at=inv.created_at,
        )  # fmt: skip
        for inv, org_name in rows
    ]


async def _seat_check(db: AsyncSession, org: Organization, role_external: bool, *, include_pending: bool,
                      ignore_invitation: OrgInvitationOrRequest | None = None) -> None:  # fmt: skip
    limits = platform.effective_limits(await platform.get_plan(db, org.plan_id), org.quota_overrides)
    roles = {r.id: r for r in await rbac.list_roles(db, org.id)}
    used = 0
    for role_id, n in (await repo.active_role_counts(db, org.id)).items():
        if bool(getattr(roles.get(role_id), "is_external_collaborator", False)) == role_external:
            used += n
    if include_pending:
        for role_id, n in (await repo.pending_invite_role_counts(db, org.id)).items():
            if bool(getattr(roles.get(role_id), "is_external_collaborator", False)) == role_external:
                used += n
        if ignore_invitation is not None:
            used -= 1
    limit = limits["max_external_collaborators" if role_external else "max_internal_seats"]
    if used + 1 > limit:
        kind = "external collaborator" if role_external else "internal seat"
        raise QuotaExceededError(f"Your plan allows {limit} {kind}s", {"limit": limit, "used": used})


async def _activate_membership(
    db: AsyncSession, ctx: TenantContext, user_id: uuid.UUID, role_id: uuid.UUID, access_expires_at: datetime | None,
) -> OrgMembership:  # fmt: skip
    existing = await repo.membership_for_user(db, ctx.org_id, user_id)
    if existing is not None and existing.status in ("ACTIVE", "SUSPENDED"):
        raise AlreadyExistsError("This person is already a member")
    if existing is not None:
        existing.role_id, existing.status = role_id, "ACTIVE"
        existing.access_expires_at, existing.joined_at = access_expires_at, _now()
        await db.flush()
        return existing
    m = OrgMembership(org_id=ctx.org_id, user_id=user_id, role_id=role_id, status="ACTIVE",
                      access_expires_at=access_expires_at)  # fmt: skip
    await repo.add(db, m)
    return m


async def accept_invitation(db: AsyncSession, principal: Principal, invitation_id: uuid.UUID) -> MyOrgOut:
    inv = await repo.get_request(db, invitation_id)
    mine = inv is not None and (inv.user_id == principal.user_id or inv.email == principal.email.lower())
    if inv is None or not mine or inv.flow_type != repo.INVITE:
        raise NotFoundError("Invitation not found")
    if inv.status != "PENDING" or inv.expires_at <= _now():
        raise InvalidStateError("This invitation is no longer valid")
    org = await repo.get_org(db, inv.org_id)
    if org is None or org.org_status in ("SUSPENDED", "ARCHIVED"):
        raise InvalidStateError("This organization is not accepting members")
    await set_tenant_scope(db, org.id, principal.user_id)
    role = await rbac.get_role(db, org.id, inv.proposed_role_id) if inv.proposed_role_id else None
    if role is None:
        raise InvalidStateError("The invited role no longer exists")
    await _seat_check(db, org, role.is_external_collaborator, include_pending=False)
    ctx = TenantContext(org_id=org.id, user_id=principal.user_id, membership_id=None, role_code=role.role_code,
                        role_id=role.id, is_external=role.is_external_collaborator, is_owner=False,
                        permissions=role.permissions, ip=principal.ip, actor_id=principal.user_id)  # fmt: skip
    m = await _activate_membership(db, ctx, principal.user_id, role.id, inv.access_expires_at)
    await rbac.grant_user_acl(db, ctx, principal.user_id, inv.acl_grants or [])
    inv.status, inv.user_id, inv.decided_by, inv.decided_at = "ACCEPTED", principal.user_id, principal.user_id, _now()
    await write_audit(db, ctx, "ORGANIZATION", "ACCEPT", "org_membership", m.id,
                      after={"role_code": role.role_code, "invitation_id": inv.id})  # fmt: skip
    return await _my_org(db, principal.user_id, org.id)


async def decline_invitation(db: AsyncSession, principal: Principal, invitation_id: uuid.UUID) -> None:
    inv = await repo.get_request(db, invitation_id)
    if (
        inv is None
        or inv.flow_type != repo.INVITE
        or not (inv.user_id == principal.user_id or inv.email == principal.email.lower())
    ):
        raise NotFoundError("Invitation not found")
    if inv.status != "PENDING":
        raise InvalidStateError("This invitation is no longer pending")
    inv.status, inv.user_id, inv.decided_by, inv.decided_at = "REJECTED", principal.user_id, principal.user_id, _now()


async def my_join_requests(db: AsyncSession, principal: Principal) -> list[MyJoinRequestOut]:
    return [
        MyJoinRequestOut(
            id=r.id, org_name=name, public_join_code=code, status=r.status, message=r.message, created_at=r.created_at
        )  # fmt: skip
        for r, name, code in await repo.join_requests_for_me(db, principal.user_id)
    ]


async def create_join_request(db: AsyncSession, principal: Principal, body: JoinRequestIn) -> MyJoinRequestOut:
    org = await repo.org_by_join_code(db, body.join_code)
    if org is None or org.org_status in ("SUSPENDED", "ARCHIVED"):
        raise NotFoundError("No organization uses this workspace code")
    m = await repo.membership_for_user(db, org.id, principal.user_id)
    if m is not None and m.status in ("ACTIVE", "SUSPENDED"):
        raise AlreadyExistsError("You are already a member of this organization")
    if await repo.pending_join_for_user(db, org.id, principal.user_id):
        raise AlreadyExistsError("You already have a pending request for this organization")
    await set_tenant_scope(db, org.id, principal.user_id)
    req = OrgInvitationOrRequest(org_id=org.id, flow_type=repo.JOIN, email=principal.email.lower(),
                                 user_id=principal.user_id, status="PENDING", message=body.message,
                                 expires_at=_now() + timedelta(days=30))  # fmt: skip
    await repo.add(db, req)
    await get_email().send(EmailMessage(org.contact_email, f"New join request for {org.legal_name}",
                                        f"{principal.email} asked to join {org.legal_name}. Review it under "
                                        "Organization > Members.", tag="JOIN_REQUEST"))  # fmt: skip
    return MyJoinRequestOut(id=req.id, org_name=org.legal_name, public_join_code=org.public_join_code,
                            status=req.status, message=req.message, created_at=req.created_at)  # fmt: skip


async def cancel_join_request(db: AsyncSession, principal: Principal, request_id: uuid.UUID) -> None:
    req = await repo.get_request(db, request_id)
    if req is None or req.flow_type != repo.JOIN or req.user_id != principal.user_id:
        raise NotFoundError()
    if req.status != "PENDING":
        raise InvalidStateError("Only pending requests can be withdrawn")
    req.status, req.decided_at = "CANCELLED", _now()


# ================================================================= tenant: context & profile
async def _org(db: AsyncSession, ctx: TenantContext) -> Organization:
    org = await repo.get_org(db, ctx.org_id)
    if org is None:
        raise NotFoundError()
    return org


async def org_context(db: AsyncSession, ctx: TenantContext) -> OrgContextOut:
    org = await _org(db, ctx)
    limits = platform.effective_limits(await platform.get_plan(db, org.plan_id), org.quota_overrides)
    fy = fy_for_date(_now().date(), org.fy_begins_from)
    imp = None
    if ctx.impersonation:
        imp = ImpersonationInfo(admin_name=ctx.impersonation.admin_name, mode=ctx.impersonation.mode,
                                expires_at=ctx.impersonation.expires_at)  # fmt: skip
    return OrgContextOut(org_id=org.id, legal_name=org.legal_name, mailing_name=org.mailing_name,
                         workspace_slug=org.workspace_slug, logo_url=await _url(org.logo_storage_key, org.logo_url),
                         state_code=org.state_code, base_currency_code=org.base_currency_code,
                         base_currency_symbol=org.base_currency_symbol, role_code=ctx.role_code,
                         role_name=ctx.role_name, is_external=ctx.is_external, is_owner=ctx.is_owner,
                         permissions={k: ctx.level(k) for k in ALL_PERMISSION_KEYS},
                         enabled_modules=limits["enabled_modules"],
                         current_fy=FyOut(label=fy.label, start=fy.start, end=fy.end),
                         books_beginning_from=org.books_beginning_from, impersonation=imp)  # fmt: skip


async def _org_out(org: Organization) -> OrgOut:
    data = {c: getattr(org, c) for c in OrgOut.model_fields if hasattr(org, c)}
    data["logo_url"] = await _url(org.logo_storage_key, org.logo_url)
    data["stamp_url"] = await _url(org.stamp_storage_key, org.company_stamp_url)
    return OrgOut(**data)


async def get_profile(db: AsyncSession, ctx: TenantContext) -> OrgOut:
    return await _org_out(await _org(db, ctx))


async def update_profile(db: AsyncSession, ctx: TenantContext, body: OrgUpdateIn) -> OrgOut:
    org = await _org(db, ctx)
    before = org.to_dict()
    data = body.model_dump(exclude_unset=True)
    for key in ("logo_storage_key", "stamp_storage_key"):
        if data.get(key):
            if not data[key].startswith(f"org/{org.id}/branding/") or await get_storage().head(data[key]) is None:
                raise ValidationFailedError("The file was not uploaded for this organization", {"field": key})
    if "state_code" in data:
        if data["state_code"] not in STATE_NAMES:
            raise ValidationFailedError("Unknown state code", {"field": "state_code"})
        org.state_name = STATE_NAMES[data["state_code"]]
    for key in ("legal_name", "address_line1", "city", "pincode", "contact_email", "contact_phone",
                "gst_reg_type", "industry_type", "state_code"):  # fmt: skip
        if key in data and data[key] is None:
            raise ValidationFailedError(f"{key} cannot be empty", {"field": key})
    for key, value in data.items():
        setattr(org, key, value)
    gstin = org.gstin
    if gstin and gstin[:2] != org.state_code:
        raise ValidationFailedError("GSTIN does not match the state code", {"field": "gstin"})
    org.updated_at = _now()
    await db.flush()
    await write_audit(db, ctx, "ORGANIZATION", "UPDATE", "organization", org.id, before=before, after=org.to_dict(),
                      changed_only=True)  # fmt: skip
    return await _org_out(org)


async def org_upload_url(ctx: TenantContext, body: OrgFileUploadIn) -> UploadTicket:
    validate_upload(body.content_type, body.size_bytes, IMAGE_MIME_ALLOWLIST, 5 * 1024 * 1024)
    ext = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}[body.content_type.split(";")[0].lower()]
    key = f"org/{ctx.org_id}/branding/{uuid.uuid4()}/{sanitize_name(body.purpose.lower() + '.' + ext)}"
    t = await get_storage().create_upload_ticket(key, body.content_type, body.size_bytes)
    return UploadTicket(upload_url=t.upload_url, method=t.method, headers=t.headers, storage_key=t.storage_key,
                        expires_at=t.expires_at)  # fmt: skip


# ================================================================= branches
async def list_branches(db: AsyncSession, ctx: TenantContext) -> list[BranchOut]:
    return [BranchOut.model_validate(b) for b in await repo.list_branches(db, ctx.org_id)]


async def create_branch(db: AsyncSession, ctx: TenantContext, body: BranchIn) -> BranchOut:
    branch = OrgBranch(org_id=ctx.org_id, **body.model_dump())
    await repo.add(db, branch)
    if branch.is_head_office:
        await repo.clear_head_office(db, ctx.org_id, branch.id)
    await write_audit(db, ctx, "ORGANIZATION", "CREATE", "org_branch", branch.id, after=branch.to_dict())
    return BranchOut.model_validate(branch)


async def update_branch(db: AsyncSession, ctx: TenantContext, branch_id: uuid.UUID, body: BranchIn) -> BranchOut:
    branch = await repo.get_branch(db, ctx.org_id, branch_id)
    if branch is None:
        raise NotFoundError()
    before = branch.to_dict()
    for k, v in body.model_dump().items():
        setattr(branch, k, v)
    await db.flush()
    if branch.is_head_office:
        await repo.clear_head_office(db, ctx.org_id, branch.id)
    await write_audit(db, ctx, "ORGANIZATION", "UPDATE", "org_branch", branch.id, before=before,
                      after=branch.to_dict(), changed_only=True)  # fmt: skip
    return BranchOut.model_validate(branch)


async def delete_branch(db: AsyncSession, ctx: TenantContext, branch_id: uuid.UUID) -> None:
    branch = await repo.get_branch(db, ctx.org_id, branch_id)
    if branch is None:
        raise NotFoundError()
    before = branch.to_dict()
    await db.delete(branch)
    await db.flush()
    await write_audit(db, ctx, "ORGANIZATION", "DELETE", "org_branch", branch_id, before=before)


# ================================================================= members
async def _members_out(db: AsyncSession, org: Organization, members: list[OrgMembership]) -> list[MemberOut]:
    roles = await rbac.roles_by_ids(db, [m.role_id for m in members])
    users = await identity.user_briefs(db, [m.user_id for m in members])
    out = []
    for m in members:
        role, user = roles.get(m.role_id), users.get(m.user_id)
        expired = m.status == "EXPIRED" or (m.access_expires_at is not None and m.access_expires_at <= _now())
        out.append(MemberOut(membership_id=m.id, user_id=m.user_id, full_name=getattr(user, "full_name", ""),
                             email=getattr(user, "email", ""), role_id=m.role_id,
                             role_code=getattr(role, "role_code", ""), role_name=getattr(role, "role_name", ""),
                             is_external=bool(getattr(role, "is_external_collaborator", False)),
                             is_owner=m.user_id == org.owner_user_id,
                             status="EXPIRED" if expired and m.status == "ACTIVE" else m.status,
                             access_expires_at=m.access_expires_at, joined_at=m.joined_at,
                             mfa_enabled=bool(getattr(user, "mfa_enabled", False))))  # fmt: skip
    return out


async def list_members(db: AsyncSession, ctx: TenantContext, q: str | None, status: str | None) -> list[MemberOut]:
    org = await _org(db, ctx)
    out = await _members_out(db, org, await repo.list_members(db, ctx.org_id, status))
    if q:
        needle = q.strip().lower()
        out = [m for m in out if needle in m.full_name.lower() or needle in m.email.lower()]
    return out


async def _member_out(db: AsyncSession, org: Organization, m: OrgMembership) -> MemberOut:
    return (await _members_out(db, org, [m]))[0]


async def update_member(
    db: AsyncSession, ctx: TenantContext, membership_id: uuid.UUID, body: MemberUpdateIn
) -> MemberOut:
    org = await _org(db, ctx)
    m = await repo.membership(db, ctx.org_id, membership_id)
    if m is None or m.status == "REVOKED":
        raise NotFoundError("Member not found")
    if m.user_id == org.owner_user_id:
        raise SystemRecordError("Use transfer ownership to change the owner")
    before = m.to_dict()
    data = body.model_dump(exclude_unset=True)
    if data.get("role_id") and data["role_id"] != m.role_id:
        role = await rbac.get_role(db, ctx.org_id, data["role_id"])
        if role is None:
            raise NotFoundError("Role not found")
        if role.role_code == "ORG_OWNER":
            raise ValidationFailedError("Use transfer ownership to make someone the owner")
        current = await rbac.get_role(db, ctx.org_id, m.role_id)
        if current is None or current.is_external_collaborator != role.is_external_collaborator:
            await _seat_check(db, org, role.is_external_collaborator, include_pending=False)
        m.role_id = role.id
    if "access_expires_at" in data:
        m.access_expires_at = data["access_expires_at"]
        if m.status == "EXPIRED" and (m.access_expires_at is None or m.access_expires_at > _now()):
            m.status = "ACTIVE"
    if data.get("status"):
        m.status = data["status"]
    await db.flush()
    await write_audit(db, ctx, "ORGANIZATION", "UPDATE", "org_membership", m.id, before=before, after=m.to_dict(),
                      changed_only=True)  # fmt: skip
    return await _member_out(db, org, m)


async def remove_member(db: AsyncSession, ctx: TenantContext, membership_id: uuid.UUID) -> None:
    org = await _org(db, ctx)
    m = await repo.membership(db, ctx.org_id, membership_id)
    if m is None or m.status == "REVOKED":
        raise NotFoundError("Member not found")
    if m.user_id == org.owner_user_id:
        raise SystemRecordError("The owner cannot be removed; transfer ownership first")
    before = m.to_dict()
    m.status = "REVOKED"
    await rbac.revoke_user_acl(db, ctx, m.user_id)
    await write_audit(db, ctx, "ORGANIZATION", "REVOKE", "org_membership", m.id, before=before, after=m.to_dict())


async def transfer_ownership(db: AsyncSession, ctx: TenantContext, body: TransferOwnershipIn) -> None:
    org = await _org(db, ctx)
    if ctx.user_id != org.owner_user_id or ctx.impersonation is not None:
        raise ForbiddenError("Only the owner can transfer ownership")
    if not await identity.check_password(ctx.user_id, body.password):
        raise InvalidCredentialsError("The password is incorrect")
    target = await repo.membership(db, ctx.org_id, body.membership_id)
    if target is None or target.status != "ACTIVE" or target.user_id == org.owner_user_id:
        raise NotFoundError("Member not found")
    target_role = await rbac.get_role(db, ctx.org_id, target.role_id)
    if target_role is None or target_role.is_external_collaborator:
        raise ValidationFailedError("External collaborators cannot own the organization")
    owner_role = await rbac.get_role_by_code(db, ctx.org_id, "ORG_OWNER")
    admin_role = await rbac.get_role_by_code(db, ctx.org_id, "ADMIN")
    current = await repo.membership_for_user(db, ctx.org_id, org.owner_user_id)
    if owner_role is None or admin_role is None or current is None:
        raise NotFoundError()
    target.role_id, current.role_id = owner_role.id, admin_role.id
    before = {"owner_user_id": org.owner_user_id}
    org.owner_user_id, org.updated_at = target.user_id, _now()
    await db.flush()
    await write_audit(db, ctx, "ORGANIZATION", "TRANSFER", "organization", org.id, before=before,
                      after={"owner_user_id": target.user_id})  # fmt: skip


# ================================================================= invitations & join requests
async def _invitations_out(db: AsyncSession, invs: list[OrgInvitationOrRequest]) -> list[InvitationOut]:
    roles = await rbac.roles_by_ids(db, [i.proposed_role_id for i in invs if i.proposed_role_id])
    users = await identity.user_briefs(db, [i.created_by for i in invs if i.created_by])
    return [
        InvitationOut(
            id=i.id,
            email=i.email,
            role_id=i.proposed_role_id,
            role_name=getattr(roles.get(i.proposed_role_id), "role_name", ""),
            status="EXPIRED" if i.status == "PENDING" and i.expires_at <= _now() else i.status,
            access_expires_at=i.access_expires_at,
            expires_at=i.expires_at,
            created_by_name=getattr(users.get(i.created_by), "full_name", None),
            created_at=i.created_at,
        )  # fmt: skip
        for i in invs
    ]


async def list_invitations(db: AsyncSession, ctx: TenantContext, status: str | None) -> list[InvitationOut]:
    return await _invitations_out(db, await repo.list_requests(db, ctx.org_id, repo.INVITE, status))


async def _send_invite_email(org: Organization, email: str, role_name: str) -> None:
    link = get_settings().PUBLIC_USER_WEB_URL.rstrip("/") + "/me/organizations"
    await get_email().send(EmailMessage(email, f"You're invited to {org.legal_name} on InaiFlow",
                                        f"You have been invited to join {org.legal_name} as {role_name}. "
                                        f"Sign in (or create an account with this email) and accept it at {link}.",
                                        tag="INVITATION"))  # fmt: skip


async def create_invitation(db: AsyncSession, ctx: TenantContext, body: InvitationIn) -> InvitationOut:
    org = await _org(db, ctx)
    email = body.email.strip().lower()
    role = await rbac.get_role(db, ctx.org_id, body.role_id)
    if role is None:
        raise NotFoundError("Role not found")
    if role.role_code == "ORG_OWNER":
        raise ValidationFailedError("Invite as another role; ownership is transferred separately")
    if body.access_expires_at is not None and body.access_expires_at <= _now():
        raise ValidationFailedError("Access expiry must be in the future")
    user = await identity.user_brief_by_email(db, email)
    if user and await repo.membership_for_user(db, ctx.org_id, user.id) and await _is_active_member(db, ctx, user.id):
        raise AlreadyExistsError("This person is already a member")
    if await repo.pending_invite_for_email(db, ctx.org_id, email):
        raise AlreadyExistsError("An invitation is already pending for this email")
    await _seat_check(db, org, role.is_external_collaborator, include_pending=True)
    inv = OrgInvitationOrRequest(org_id=ctx.org_id, flow_type=repo.INVITE, email=email,
                                 user_id=user.id if user else None, proposed_role_id=role.id, status="PENDING",
                                 access_expires_at=body.access_expires_at, created_by=ctx.user_id,
                                 expires_at=_now() + INVITE_TTL,
                                 acl_grants=[g.model_dump(mode="json") for g in body.acl_grants] or None)  # fmt: skip
    await repo.add(db, inv)
    await write_audit(db, ctx, "ORGANIZATION", "INVITE", "org_invitation", inv.id, after=inv.to_dict())
    await _send_invite_email(org, email, role.role_name)
    return (await _invitations_out(db, [inv]))[0]


async def _is_active_member(db: AsyncSession, ctx: TenantContext, user_id: uuid.UUID) -> bool:
    m = await repo.membership_for_user(db, ctx.org_id, user_id)
    return m is not None and m.status in ("ACTIVE", "SUSPENDED")


async def resend_invitation(db: AsyncSession, ctx: TenantContext, invitation_id: uuid.UUID) -> None:
    org = await _org(db, ctx)
    inv = await repo.get_request(db, invitation_id, ctx.org_id)
    if inv is None or inv.flow_type != repo.INVITE:
        raise NotFoundError()
    if inv.status not in ("PENDING", "EXPIRED"):
        raise InvalidStateError("Only pending invitations can be resent")
    inv.status, inv.expires_at = "PENDING", _now() + INVITE_TTL
    role = await rbac.get_role(db, ctx.org_id, inv.proposed_role_id) if inv.proposed_role_id else None
    await _send_invite_email(org, inv.email, role.role_name if role else "member")


async def cancel_invitation(db: AsyncSession, ctx: TenantContext, invitation_id: uuid.UUID) -> None:
    inv = await repo.get_request(db, invitation_id, ctx.org_id)
    if inv is None or inv.flow_type != repo.INVITE:
        raise NotFoundError()
    if inv.status != "PENDING":
        raise InvalidStateError("Only pending invitations can be cancelled")
    inv.status, inv.decided_by, inv.decided_at = "CANCELLED", ctx.user_id, _now()
    await write_audit(db, ctx, "ORGANIZATION", "DELETE", "org_invitation", inv.id, after={"status": "CANCELLED"})


async def list_join_requests(db: AsyncSession, ctx: TenantContext, status: str | None) -> list[JoinRequestOut]:
    reqs = await repo.list_requests(db, ctx.org_id, repo.JOIN, status)
    users = await identity.user_briefs(db, [r.user_id for r in reqs if r.user_id])
    out = []
    for r in reqs:
        u = users.get(r.user_id)
        out.append(JoinRequestOut(id=r.id, user_id=r.user_id, full_name=getattr(u, "full_name", ""), email=r.email,
                                  is_email_verified=bool(getattr(u, "is_email_verified", False)),
                                  professional_reg_no=getattr(u, "professional_reg_no", None), message=r.message,
                                  status=r.status, created_at=r.created_at))  # fmt: skip
    return out


async def approve_join_request(
    db: AsyncSession, ctx: TenantContext, request_id: uuid.UUID, body: JoinDecisionIn
) -> MemberOut:
    org = await _org(db, ctx)
    req = await repo.get_request(db, request_id, ctx.org_id)
    if req is None or req.flow_type != repo.JOIN or req.user_id is None:
        raise NotFoundError()
    if req.status != "PENDING":
        raise InvalidStateError("This request was already decided")
    role = await rbac.get_role(db, ctx.org_id, body.role_id)
    if role is None:
        raise NotFoundError("Role not found")
    if role.role_code == "ORG_OWNER":
        raise ValidationFailedError("Ownership is transferred separately")
    await _seat_check(db, org, role.is_external_collaborator, include_pending=False)
    m = await _activate_membership(db, ctx, req.user_id, role.id, body.access_expires_at)
    req.status, req.proposed_role_id, req.decided_by, req.decided_at = "ACCEPTED", role.id, ctx.user_id, _now()
    req.access_expires_at = body.access_expires_at
    await write_audit(db, ctx, "ORGANIZATION", "APPROVE", "org_join_request", req.id,
                      after={"membership_id": m.id, "role_code": role.role_code})  # fmt: skip
    return await _member_out(db, org, m)


async def reject_join_request(db: AsyncSession, ctx: TenantContext, request_id: uuid.UUID) -> None:
    req = await repo.get_request(db, request_id, ctx.org_id)
    if req is None or req.flow_type != repo.JOIN:
        raise NotFoundError()
    if req.status != "PENDING":
        raise InvalidStateError("This request was already decided")
    req.status, req.decided_by, req.decided_at = "REJECTED", ctx.user_id, _now()
    await write_audit(db, ctx, "ORGANIZATION", "REJECT", "org_join_request", req.id, after={"status": "REJECTED"})


# ================================================================= security, audit, billing
def _security(org: Organization) -> SecuritySettings:
    merged = {**DEFAULT_SECURITY, **(org.security_settings or {})}
    return SecuritySettings(**{k: merged[k] for k in DEFAULT_SECURITY})


async def get_security(db: AsyncSession, ctx: TenantContext) -> SecuritySettings:
    return _security(await _org(db, ctx))


async def put_security(db: AsyncSession, ctx: TenantContext, body: SecuritySettings) -> SecuritySettings:
    org = await _org(db, ctx)
    before = dict(org.security_settings or {})
    after = body.model_dump(mode="json")
    org.security_settings = {**before, **after}
    org.updated_at = _now()
    await db.flush()
    await write_audit(db, ctx, "ORGANIZATION", "UPDATE", "security_settings", org.id, before=before, after=after,
                      changed_only=True)  # fmt: skip
    return _security(org)


def audit_out(row: Any, user_names: dict[uuid.UUID, str]) -> AuditLogOut:
    return AuditLogOut(id=row.id, module=row.module, action=row.action, entity_type=row.entity_type,
                       entity_id=row.entity_id, actor_type=row.actor_type, user_id=row.user_id,
                       user_name=user_names.get(row.user_id) if row.user_id else None, role_code=row.role_code,
                       before_diff=row.before_diff, after_diff=row.after_diff, reason=row.reason,
                       ip_address=str(row.ip_address) if row.ip_address else None, created_at=row.created_at)  # fmt: skip


async def _audit_out(db: AsyncSession, rows: list[Any]) -> list[AuditLogOut]:
    users = await identity.user_briefs(db, [r.user_id for r in rows if r.user_id])
    names = {k: v.full_name for k, v in users.items()}
    return [audit_out(r, names) for r in rows]


async def audit_logs(
    db: AsyncSession, ctx: TenantContext, *, limit: int, offset: int, **filters: Any
) -> Page[AuditLogOut]:
    rows, total = await repo.audit_page(db, ctx.org_id, limit=limit, offset=offset, **filters)
    return Page[AuditLogOut](items=await _audit_out(db, rows), total=total, limit=limit, offset=offset)


async def entity_audit_trail(
    db: AsyncSession, ctx: TenantContext, entity_type: str, entity_id: uuid.UUID
) -> list[AuditLogOut]:
    return await _audit_out(db, await repo.audit_for_entity(db, ctx.org_id, entity_type, entity_id))


async def billing(db: AsyncSession, ctx: TenantContext) -> BillingOut:
    org = await _org(db, ctx)
    plan = await platform.get_plan(db, org.plan_id)
    limits = platform.effective_limits(plan, org.quota_overrides)
    roles = {r.id: r for r in await rbac.list_roles(db, org.id)}
    internal = external = 0
    for role_id, n in (await repo.active_role_counts(db, org.id)).items():
        if getattr(roles.get(role_id), "is_external_collaborator", False):
            external += n
        else:
            internal += n
    return BillingOut(plan_code=plan.plan_code if plan else None, plan_name=plan.name if plan else None,
                      org_status=org.org_status, trial_ends_at=org.trial_ends_at, internal_seats_used=internal,
                      internal_seats_max=limits["max_internal_seats"], external_seats_used=external,
                      external_seats_max=limits["max_external_collaborators"],
                      storage_used_bytes=await documents.storage_used_bytes(db, ctx),
                      storage_max_gb=limits["max_storage_gb"], enabled_modules=limits["enabled_modules"])  # fmt: skip
