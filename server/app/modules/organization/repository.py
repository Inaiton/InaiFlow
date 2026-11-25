"""Organization data access. Never commits. Only this module's tables: names of users/roles are resolved by
the service through ``identity.interface`` / ``rbac.interface``."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.organization.models import (
    Organization,
    OrgAuditLog,
    OrgBranch,
    OrgInvitationOrRequest,
    OrgMembership,
)

INVITE, JOIN = "INVITE_PUSH", "JOIN_REQUEST_PULL"


async def add(db: AsyncSession, obj: object) -> None:
    db.add(obj)
    await db.flush()


# ---------------------------------------------------------------- organizations
async def get_org(db: AsyncSession, org_id: uuid.UUID) -> Organization | None:
    return await db.get(Organization, org_id)


async def slug_taken(db: AsyncSession, slug: str) -> bool:
    return (await db.execute(select(Organization.id).where(Organization.workspace_slug == slug))).first() is not None


async def join_code_taken(db: AsyncSession, code: str) -> bool:
    return (await db.execute(select(Organization.id).where(Organization.public_join_code == code))).first() is not None


async def org_by_join_code(db: AsyncSession, code: str) -> Organization | None:
    return (
        await db.execute(select(Organization).where(Organization.public_join_code == code.strip().upper()))
    ).scalar_one_or_none()


async def active_org_ids(db: AsyncSession) -> list[uuid.UUID]:
    rows = await db.execute(select(Organization.id).where(Organization.org_status.in_(("ACTIVE", "TRIAL"))))
    return list(rows.scalars())


# ---------------------------------------------------------------- memberships
async def list_members(db: AsyncSession, org_id: uuid.UUID, status: str | None) -> list[OrgMembership]:
    stmt = select(OrgMembership).where(OrgMembership.org_id == org_id)
    stmt = stmt.where(OrgMembership.status == status) if status else stmt.where(OrgMembership.status != "REVOKED")
    return list((await db.execute(stmt.order_by(OrgMembership.joined_at))).scalars())


async def membership(db: AsyncSession, org_id: uuid.UUID, membership_id: uuid.UUID) -> OrgMembership | None:
    return (
        await db.execute(
            select(OrgMembership)
            .where(OrgMembership.org_id == org_id, OrgMembership.id == membership_id)
            .with_for_update()
        )
    ).scalar_one_or_none()


async def membership_for_user(db: AsyncSession, org_id: uuid.UUID, user_id: uuid.UUID) -> OrgMembership | None:
    return (
        await db.execute(select(OrgMembership).where(OrgMembership.org_id == org_id, OrgMembership.user_id == user_id))
    ).scalar_one_or_none()


async def my_orgs(db: AsyncSession, user_id: uuid.UUID, org_id: uuid.UUID | None = None) -> list[Any]:
    stmt = (
        select(OrgMembership, Organization)
        .join(Organization, Organization.id == OrgMembership.org_id)
        .where(OrgMembership.user_id == user_id, OrgMembership.status != "REVOKED")
    )
    if org_id is not None:
        stmt = stmt.where(OrgMembership.org_id == org_id)
    return list((await db.execute(stmt.order_by(Organization.legal_name))).all())


async def active_role_counts(db: AsyncSession, org_id: uuid.UUID) -> dict[uuid.UUID, int]:
    rows = await db.execute(
        select(OrgMembership.role_id, func.count())
        .where(OrgMembership.org_id == org_id, OrgMembership.status == "ACTIVE")
        .group_by(OrgMembership.role_id)
    )
    return {r[0]: int(r[1]) for r in rows.all()}


async def pending_invite_role_counts(db: AsyncSession, org_id: uuid.UUID) -> dict[uuid.UUID, int]:
    rows = await db.execute(
        select(OrgInvitationOrRequest.proposed_role_id, func.count())
        .where(
            OrgInvitationOrRequest.org_id == org_id,
            OrgInvitationOrRequest.flow_type == INVITE,
            OrgInvitationOrRequest.status == "PENDING",
            OrgInvitationOrRequest.expires_at > func.now(),
        )  # fmt: skip
        .group_by(OrgInvitationOrRequest.proposed_role_id)
    )
    return {r[0]: int(r[1]) for r in rows.all()}


async def member_counts_by_role(db: AsyncSession, org_id: uuid.UUID) -> dict[uuid.UUID, int]:
    rows = await db.execute(
        select(OrgMembership.role_id, func.count())
        .where(OrgMembership.org_id == org_id, OrgMembership.status.in_(("ACTIVE", "SUSPENDED")))
        .group_by(OrgMembership.role_id)
    )
    return {r[0]: int(r[1]) for r in rows.all()}


# ---------------------------------------------------------------- invitations & join requests
async def get_request(
    db: AsyncSession, request_id: uuid.UUID, org_id: uuid.UUID | None = None
) -> OrgInvitationOrRequest | None:
    stmt = select(OrgInvitationOrRequest).where(OrgInvitationOrRequest.id == request_id)
    if org_id is not None:
        stmt = stmt.where(OrgInvitationOrRequest.org_id == org_id)
    return (await db.execute(stmt.with_for_update())).scalar_one_or_none()


async def list_requests(
    db: AsyncSession, org_id: uuid.UUID, flow: str, status: str | None
) -> list[OrgInvitationOrRequest]:
    stmt = select(OrgInvitationOrRequest).where(
        OrgInvitationOrRequest.org_id == org_id, OrgInvitationOrRequest.flow_type == flow
    )
    if status:
        stmt = stmt.where(OrgInvitationOrRequest.status == status)
    return list((await db.execute(stmt.order_by(OrgInvitationOrRequest.created_at.desc()))).scalars())


async def pending_invite_for_email(db: AsyncSession, org_id: uuid.UUID, email: str) -> OrgInvitationOrRequest | None:
    return (
        (
            await db.execute(
                select(OrgInvitationOrRequest).where(
                    OrgInvitationOrRequest.org_id == org_id,
                    OrgInvitationOrRequest.flow_type == INVITE,
                    OrgInvitationOrRequest.email == email,
                    OrgInvitationOrRequest.status == "PENDING",
                    OrgInvitationOrRequest.expires_at > func.now(),
                )  # fmt: skip
            )
        )
        .scalars()
        .first()
    )


async def pending_join_for_user(
    db: AsyncSession, org_id: uuid.UUID, user_id: uuid.UUID
) -> OrgInvitationOrRequest | None:
    return (
        (
            await db.execute(
                select(OrgInvitationOrRequest).where(
                    OrgInvitationOrRequest.org_id == org_id,
                    OrgInvitationOrRequest.flow_type == JOIN,
                    OrgInvitationOrRequest.user_id == user_id,
                    OrgInvitationOrRequest.status == "PENDING",
                )  # fmt: skip
            )
        )
        .scalars()
        .first()
    )


async def invitations_for_me(db: AsyncSession, user_id: uuid.UUID, email: str) -> list[Any]:
    stmt = (
        select(OrgInvitationOrRequest, Organization.legal_name)
        .join(Organization, Organization.id == OrgInvitationOrRequest.org_id)
        .where(
            OrgInvitationOrRequest.flow_type == INVITE,
            OrgInvitationOrRequest.status == "PENDING",
            OrgInvitationOrRequest.expires_at > func.now(),
            or_(OrgInvitationOrRequest.user_id == user_id, OrgInvitationOrRequest.email == email),
        )  # fmt: skip
        .order_by(OrgInvitationOrRequest.created_at.desc())
    )
    return list((await db.execute(stmt)).all())


async def join_requests_for_me(db: AsyncSession, user_id: uuid.UUID) -> list[Any]:
    stmt = (
        select(OrgInvitationOrRequest, Organization.legal_name, Organization.public_join_code)
        .join(Organization, Organization.id == OrgInvitationOrRequest.org_id)
        .where(OrgInvitationOrRequest.flow_type == JOIN, OrgInvitationOrRequest.user_id == user_id)
        .order_by(OrgInvitationOrRequest.created_at.desc())
    )
    return list((await db.execute(stmt)).all())


async def expire_invitations(db: AsyncSession) -> int:
    res = await db.execute(
        update(OrgInvitationOrRequest)
        .where(OrgInvitationOrRequest.status == "PENDING", OrgInvitationOrRequest.expires_at <= func.now())
        .values(status="EXPIRED")
    )
    return int(res.rowcount or 0)


async def expire_memberships(db: AsyncSession) -> int:
    res = await db.execute(
        update(OrgMembership)
        .where(
            OrgMembership.status == "ACTIVE",
            OrgMembership.access_expires_at.is_not(None),
            OrgMembership.access_expires_at <= func.now(),
        )  # fmt: skip
        .values(status="EXPIRED")
    )
    return int(res.rowcount or 0)


# ---------------------------------------------------------------- branches
async def list_branches(db: AsyncSession, org_id: uuid.UUID) -> list[OrgBranch]:
    rows = await db.execute(select(OrgBranch).where(OrgBranch.org_id == org_id).order_by(OrgBranch.created_at))
    return list(rows.scalars())


async def get_branch(db: AsyncSession, org_id: uuid.UUID, branch_id: uuid.UUID) -> OrgBranch | None:
    return (
        await db.execute(select(OrgBranch).where(OrgBranch.org_id == org_id, OrgBranch.id == branch_id))
    ).scalar_one_or_none()


async def clear_head_office(db: AsyncSession, org_id: uuid.UUID, except_id: uuid.UUID | None) -> None:
    stmt = update(OrgBranch).where(OrgBranch.org_id == org_id, OrgBranch.is_head_office)
    if except_id is not None:
        stmt = stmt.where(OrgBranch.id != except_id)
    await db.execute(stmt.values(is_head_office=False))


# ---------------------------------------------------------------- audit
async def audit_page(
    db: AsyncSession, org_id: uuid.UUID, *, module: str | None, action: str | None, entity_type: str | None,
    entity_id: uuid.UUID | None, user_id: uuid.UUID | None, date_from: date | None, date_to: date | None,
    limit: int, offset: int,
) -> tuple[list[OrgAuditLog], int]:  # fmt: skip
    stmt = select(OrgAuditLog).where(OrgAuditLog.org_id == org_id)
    for col, value in ((OrgAuditLog.module, module), (OrgAuditLog.action, action),
                       (OrgAuditLog.entity_type, entity_type), (OrgAuditLog.entity_id, entity_id),
                       (OrgAuditLog.user_id, user_id)):  # fmt: skip
        if value is not None:
            stmt = stmt.where(col == value)
    if date_from:
        stmt = stmt.where(OrgAuditLog.created_at >= datetime.combine(date_from, datetime.min.time()))
    if date_to:
        stmt = stmt.where(func.date(OrgAuditLog.created_at) <= date_to)
    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = await db.execute(stmt.order_by(OrgAuditLog.created_at.desc(), OrgAuditLog.id).limit(limit).offset(offset))
    return list(rows.scalars()), int(total)


async def audit_for_entity(
    db: AsyncSession, org_id: uuid.UUID, entity_type: str, entity_id: uuid.UUID
) -> list[OrgAuditLog]:
    stmt = select(OrgAuditLog).where(
        OrgAuditLog.org_id == org_id, OrgAuditLog.entity_type == entity_type, OrgAuditLog.entity_id == entity_id
    )
    return list((await db.execute(stmt.order_by(OrgAuditLog.created_at))).scalars())


async def release_role(db: AsyncSession, org_id: uuid.UUID, role_id: uuid.UUID) -> None:
    """Drop references to a role being deleted: revoked/expired memberships go, pending invites are cancelled."""
    from sqlalchemy import delete

    await db.execute(
        delete(OrgMembership).where(
            OrgMembership.org_id == org_id,
            OrgMembership.role_id == role_id,
            OrgMembership.status.in_(("REVOKED", "EXPIRED")),
        )  # fmt: skip
    )
    await db.execute(
        update(OrgInvitationOrRequest)
        .where(OrgInvitationOrRequest.org_id == org_id, OrgInvitationOrRequest.proposed_role_id == role_id)
        .values(
            proposed_role_id=None,
            status=func.coalesce(func.nullif(OrgInvitationOrRequest.status, "PENDING"), "CANCELLED"),
        )  # fmt: skip
    )
