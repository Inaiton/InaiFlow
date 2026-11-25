"""Roles (permission matrices) and record-level ACL overrides."""

from __future__ import annotations

import uuid
from collections.abc import Iterable

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import write_audit
from app.core.context import TenantContext
from app.core.errors import (
    AlreadyExistsError,
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    SystemRecordError,
    ValidationFailedError,
)
from app.core.permissions import effective_permissions, validate_permission_map
from app.modules.accounts import interface as accounts
from app.modules.documents import interface as documents
from app.modules.identity import interface as identity
from app.modules.operations import interface as operations
from app.modules.organization import interface as organization
from app.modules.platform.interface import list_configs
from app.modules.rbac import repository as repo
from app.modules.rbac.models import OrgRole
from app.modules.rbac.schemas import AclIn, AclOut, RoleIn, RoleOut, RoleUpdateIn

RESERVED_CODES = {"ORG_OWNER", "ADMIN", "ACCOUNTANT", "QA_LEAD", "OPERATOR", "AUDITOR", "SYSTEM",
                  "SUPPORT_IMPERSONATION"}  # fmt: skip


def _full_matrix(perms: dict | None) -> dict[str, str]:
    return effective_permissions(perms or {}, is_owner=False)


def _role_out(role: OrgRole, member_count: int) -> RoleOut:
    perms = effective_permissions(role.permissions, is_owner=role.role_code == "ORG_OWNER")
    return RoleOut(id=role.id, role_code=role.role_code, role_name=role.role_name,
                   is_system_role=role.is_system_role, is_external_collaborator=role.is_external_collaborator,
                   permissions=perms, member_count=member_count)  # fmt: skip


async def seed_org_roles(db: AsyncSession, ctx: TenantContext) -> dict[str, uuid.UUID]:
    out: dict[str, uuid.UUID] = {}
    for _, payload in await list_configs(db, "DEFAULT_ROLES"):
        role = await repo.add_role(
            db,
            OrgRole(
                org_id=ctx.org_id,
                role_code=payload["role_code"],
                role_name=payload["role_name"],
                is_system_role=True,
                is_external_collaborator=bool(payload.get("is_external_collaborator")),
                permissions=_full_matrix(payload.get("permissions")),
            ),  # fmt: skip
        )
        out[role.role_code] = role.id
    return out


async def list_roles(db: AsyncSession, ctx: TenantContext) -> list[RoleOut]:
    counts = await organization.member_counts_by_role(db, ctx.org_id)
    return [_role_out(r, counts.get(r.id, 0)) for r in await repo.list_roles(db, ctx.org_id)]


async def _role_or_404(db: AsyncSession, ctx: TenantContext, role_id: uuid.UUID) -> OrgRole:
    role = await repo.get_role(db, ctx.org_id, role_id)
    if role is None:
        raise NotFoundError("Role not found")
    return role


def _validated(perms: dict[str, str], *, full: bool = True) -> dict[str, str]:
    try:
        checked = validate_permission_map(perms)
    except ValueError as exc:
        raise ValidationFailedError(str(exc)) from exc
    return _full_matrix(checked) if full else checked


async def create_role(db: AsyncSession, ctx: TenantContext, body: RoleIn) -> RoleOut:
    if body.role_code in RESERVED_CODES:
        raise ValidationFailedError("This role code is reserved")
    if await repo.get_role_by_code(db, ctx.org_id, body.role_code):
        raise AlreadyExistsError("A role with this code already exists")
    role = await repo.add_role(
        db,
        OrgRole(org_id=ctx.org_id, role_code=body.role_code, role_name=body.role_name, is_system_role=False,
                is_external_collaborator=body.is_external_collaborator, permissions=_validated(body.permissions)),
    )  # fmt: skip
    await write_audit(db, ctx, "ORGANIZATION", "CREATE", "org_role", role.id, after=role.to_dict())
    return _role_out(role, 0)


async def update_role(db: AsyncSession, ctx: TenantContext, role_id: uuid.UUID, body: RoleUpdateIn) -> RoleOut:
    role = await _role_or_404(db, ctx, role_id)
    if role.role_code == "ORG_OWNER":
        raise SystemRecordError("The owner role always has full control")
    if role.id == ctx.role_id and not ctx.is_owner and body.permissions is not None:
        raise PermissionDeniedError(details={"reason": "You cannot change the permissions of your own role"})
    before = role.to_dict()
    if body.role_name is not None:
        role.role_name = body.role_name
    if body.is_external_collaborator is not None:
        role.is_external_collaborator = body.is_external_collaborator
    if body.permissions is not None:
        role.permissions = {**_full_matrix(role.permissions), **_validated(body.permissions, full=False)}
    await db.flush()
    await write_audit(db, ctx, "ORGANIZATION", "UPDATE", "org_role", role.id, before=before, after=role.to_dict(),
                      changed_only=True)  # fmt: skip
    counts = await organization.member_counts_by_role(db, ctx.org_id)
    return _role_out(role, counts.get(role.id, 0))


async def delete_role(db: AsyncSession, ctx: TenantContext, role_id: uuid.UUID) -> None:
    role = await _role_or_404(db, ctx, role_id)
    if role.is_system_role:
        raise SystemRecordError("System roles cannot be deleted")
    counts = await organization.member_counts_by_role(db, ctx.org_id)
    if counts.get(role.id, 0) > 0:
        raise ConflictError("Move members to another role before deleting this one")
    before = role.to_dict()
    await organization.release_role(db, ctx.org_id, role.id)
    await repo.delete_role(db, role)
    await write_audit(db, ctx, "ORGANIZATION", "DELETE", "org_role", role_id, before=before)


# ---------------------------------------------------------------- ACL
async def _resource_names(db: AsyncSession, ctx: TenantContext, rtype: str, ids: list[uuid.UUID]) -> dict:
    if not ids:
        return {}
    if rtype in ("STOCK_ITEM", "GODOWN"):
        return await accounts.resource_names(db, ctx, rtype, ids)
    if rtype == "PERIOD_RUN":
        return await operations.resource_names(db, ctx, rtype, ids)
    if rtype == "DOC_FOLDER":
        return await documents.resource_names(db, ctx, rtype, ids)
    return {}


async def _acl_out(db: AsyncSession, ctx: TenantContext, rows: list) -> list[AclOut]:
    roles = {r.id: r.role_name for r in await repo.list_roles(db, ctx.org_id)}
    users = await identity.user_briefs(db, [r.subject_id for r in rows if r.subject_type == "USER"])
    names: dict[uuid.UUID, str] = {}
    for rtype in {r.resource_type for r in rows}:
        names.update(await _resource_names(db, ctx, rtype, [r.resource_id for r in rows if r.resource_type == rtype]))
    out = []
    for r in rows:
        subject = (
            roles.get(r.subject_id) if r.subject_type == "ROLE" else getattr(users.get(r.subject_id), "full_name", None)
        )
        out.append(AclOut(id=r.id, subject_type=r.subject_type, subject_id=r.subject_id,
                          subject_name=subject or "(removed)", resource_type=r.resource_type,
                          resource_id=r.resource_id, resource_name=names.get(r.resource_id, "(removed)"),
                          access_level=r.access_level, created_at=r.created_at))  # fmt: skip
    return out


async def list_acl(
    db: AsyncSession, ctx: TenantContext, subject_type: str | None, subject_id: uuid.UUID | None,
    resource_type: str | None,
) -> list[AclOut]:  # fmt: skip
    return await _acl_out(db, ctx, await repo.list_acl(db, ctx.org_id, subject_type, subject_id, resource_type))


async def _validate_subject(db: AsyncSession, ctx: TenantContext, subject_type: str, subject_id: uuid.UUID) -> None:
    if subject_type == "ROLE":
        role = await repo.get_role(db, ctx.org_id, subject_id)
        if role is None:
            raise NotFoundError("Role not found")
        if role.role_code == "ORG_OWNER":
            raise SystemRecordError("The owner role always has full control")
    elif not await organization.is_member(db, ctx.org_id, subject_id):
        raise NotFoundError("Member not found")


async def put_acl(db: AsyncSession, ctx: TenantContext, body: AclIn) -> AclOut:
    await _validate_subject(db, ctx, body.subject_type, body.subject_id)
    if not await _resource_names(db, ctx, body.resource_type, [body.resource_id]):
        raise NotFoundError("Resource not found")
    existing = await repo.find_acl(db, ctx.org_id, body.subject_type, body.subject_id, body.resource_type,
                                   body.resource_id)  # fmt: skip
    before = existing.to_dict() if existing else None
    acl_id = await repo.upsert_acl(db, ctx.org_id, body.subject_type, body.subject_id, body.resource_type,
                                   body.resource_id, body.access_level)  # fmt: skip
    acl = await repo.get_acl(db, ctx.org_id, acl_id)
    if acl is None:
        raise NotFoundError()
    await db.refresh(acl)
    await write_audit(db, ctx, "ORGANIZATION", "UPDATE" if before else "CREATE", "resource_acl", acl_id,
                      before=before, after=acl.to_dict())  # fmt: skip
    return (await _acl_out(db, ctx, [acl]))[0]


async def delete_acl(db: AsyncSession, ctx: TenantContext, acl_id: uuid.UUID) -> None:
    acl = await repo.get_acl(db, ctx.org_id, acl_id)
    if acl is None:
        raise NotFoundError()
    before = acl.to_dict()
    await repo.delete_acl(db, acl)
    await write_audit(db, ctx, "ORGANIZATION", "DELETE", "resource_acl", acl_id, before=before)


async def grant_user_acl(db: AsyncSession, ctx: TenantContext, user_id: uuid.UUID, grants: Iterable[dict]) -> int:
    """Apply invitation ``acl_grants`` ([{resource_type, resource_id, access_level}]) for a new member."""
    n = 0
    for g in grants or []:
        rtype, rid, level = g.get("resource_type"), g.get("resource_id"), g.get("access_level")
        if rtype not in ("STOCK_ITEM", "PERIOD_RUN", "DOC_FOLDER", "GODOWN") or level not in (
            "NONE",
            "READ",
            "WRITE",
            "FULL",
        ):
            continue
        await repo.upsert_acl(db, ctx.org_id, "USER", user_id, rtype, uuid.UUID(str(rid)), level)
        n += 1
    return n


async def revoke_user_acl(db: AsyncSession, ctx: TenantContext, user_id: uuid.UUID) -> None:
    await repo.delete_user_acl(db, ctx.org_id, user_id)
