"""RBAC data access. Never commits."""

from __future__ import annotations

import uuid

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.rbac.models import OrgRole, ResourceAcl


async def list_roles(db: AsyncSession, org_id: uuid.UUID) -> list[OrgRole]:
    rows = await db.execute(
        select(OrgRole).where(OrgRole.org_id == org_id).order_by(OrgRole.created_at, OrgRole.role_code)
    )
    return list(rows.scalars())


async def get_role(db: AsyncSession, org_id: uuid.UUID, role_id: uuid.UUID) -> OrgRole | None:
    return (
        await db.execute(select(OrgRole).where(OrgRole.org_id == org_id, OrgRole.id == role_id))
    ).scalar_one_or_none()


async def get_role_by_code(db: AsyncSession, org_id: uuid.UUID, code: str) -> OrgRole | None:
    return (
        await db.execute(select(OrgRole).where(OrgRole.org_id == org_id, OrgRole.role_code == code))
    ).scalar_one_or_none()


async def add_role(db: AsyncSession, role: OrgRole) -> OrgRole:
    db.add(role)
    await db.flush()
    return role


async def delete_role(db: AsyncSession, role: OrgRole) -> None:
    await db.execute(
        delete(ResourceAcl).where(
            ResourceAcl.org_id == role.org_id, ResourceAcl.subject_type == "ROLE", ResourceAcl.subject_id == role.id
        )
    )
    await db.delete(role)
    await db.flush()


async def list_acl(
    db: AsyncSession,
    org_id: uuid.UUID,
    subject_type: str | None,
    subject_id: uuid.UUID | None,
    resource_type: str | None,
) -> list[ResourceAcl]:
    stmt = select(ResourceAcl).where(ResourceAcl.org_id == org_id)
    if subject_type:
        stmt = stmt.where(ResourceAcl.subject_type == subject_type)
    if subject_id:
        stmt = stmt.where(ResourceAcl.subject_id == subject_id)
    if resource_type:
        stmt = stmt.where(ResourceAcl.resource_type == resource_type)
    return list((await db.execute(stmt.order_by(ResourceAcl.created_at))).scalars())


async def get_acl(db: AsyncSession, org_id: uuid.UUID, acl_id: uuid.UUID) -> ResourceAcl | None:
    return (
        await db.execute(select(ResourceAcl).where(ResourceAcl.org_id == org_id, ResourceAcl.id == acl_id))
    ).scalar_one_or_none()


async def find_acl(
    db: AsyncSession, org_id: uuid.UUID, subject_type: str, subject_id: uuid.UUID, rtype: str, rid: uuid.UUID
) -> ResourceAcl | None:
    return (
        await db.execute(
            select(ResourceAcl).where(
                ResourceAcl.org_id == org_id,
                ResourceAcl.subject_type == subject_type,
                ResourceAcl.subject_id == subject_id,
                ResourceAcl.resource_type == rtype,
                ResourceAcl.resource_id == rid,
            )
        )
    ).scalar_one_or_none()


async def upsert_acl(
    db: AsyncSession, org_id: uuid.UUID, subject_type: str, subject_id: uuid.UUID, rtype: str, rid: uuid.UUID,
    level: str,
) -> uuid.UUID:  # fmt: skip
    stmt = (
        insert(ResourceAcl)
        .values(
            org_id=org_id,
            subject_type=subject_type,
            subject_id=subject_id,
            resource_type=rtype,
            resource_id=rid,
            access_level=level,
        )  # fmt: skip
        .on_conflict_do_update(constraint="uq_resource_acl_subject_resource", set_={"access_level": level})
        .returning(ResourceAcl.id)
    )
    return (await db.execute(stmt)).scalar_one()


async def delete_acl(db: AsyncSession, acl: ResourceAcl) -> None:
    await db.delete(acl)
    await db.flush()


async def delete_user_acl(db: AsyncSession, org_id: uuid.UUID, user_id: uuid.UUID) -> None:
    await db.execute(
        delete(ResourceAcl).where(
            ResourceAcl.org_id == org_id, ResourceAcl.subject_type == "USER", ResourceAcl.subject_id == user_id
        )
    )


async def roles_by_ids(db: AsyncSession, role_ids: list[uuid.UUID]) -> list[OrgRole]:
    ids = list({i for i in role_ids if i})
    if not ids:
        return []
    return list((await db.execute(select(OrgRole).where(OrgRole.id.in_(ids)))).scalars())
