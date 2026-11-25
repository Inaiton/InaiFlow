"""Public API of the rbac module."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import TenantContext
from app.core.deps import acl_overrides, resource_level
from app.core.permissions import effective_level, effective_permissions, resolve_resource_level
from app.modules.rbac import repository as _repo
from app.modules.rbac.service import grant_user_acl, revoke_user_acl, seed_org_roles


@dataclass(frozen=True, slots=True)
class RoleDTO:
    id: uuid.UUID
    role_code: str
    role_name: str
    is_system_role: bool
    is_external_collaborator: bool
    permissions: dict[str, str]


def _dto(role) -> RoleDTO:  # noqa: ANN001
    return RoleDTO(role.id, role.role_code, role.role_name, role.is_system_role, role.is_external_collaborator,
                   effective_permissions(role.permissions, is_owner=role.role_code == "ORG_OWNER"))  # fmt: skip


async def get_role(db: AsyncSession, org_id: uuid.UUID, role_id: uuid.UUID) -> RoleDTO | None:
    role = await _repo.get_role(db, org_id, role_id)
    return _dto(role) if role else None


async def get_role_by_code(db: AsyncSession, org_id: uuid.UUID, code: str) -> RoleDTO | None:
    role = await _repo.get_role_by_code(db, org_id, code)
    return _dto(role) if role else None


async def list_roles(db: AsyncSession, org_id: uuid.UUID) -> list[RoleDTO]:
    return [_dto(r) for r in await _repo.list_roles(db, org_id)]


async def resource_levels(
    db: AsyncSession, ctx: TenantContext, resource_type: str, resource_ids: list[uuid.UUID], module_key: str
) -> dict[uuid.UUID, str]:
    """Effective level per resource id for the caller (ACL overrides applied)."""
    if ctx.is_owner:
        return dict.fromkeys(resource_ids, "FULL")
    overrides = await acl_overrides(ctx, db, resource_type, resource_ids)
    module = ctx.level(module_key)
    return {rid: overrides.get(rid, module) for rid in resource_ids}


__all__ = [
    "RoleDTO",
    "effective_level",
    "get_role",
    "get_role_by_code",
    "grant_user_acl",
    "list_roles",
    "resolve_resource_level",
    "resource_level",
    "resource_levels",
    "revoke_user_acl",
    "roles_by_ids",
    "seed_org_roles",
]


async def roles_by_ids(db: AsyncSession, role_ids: list[uuid.UUID]) -> dict[uuid.UUID, RoleDTO]:
    """Roles by id (any org visible to the session; RLS limits the app role to the current org)."""
    return {r.id: _dto(r) for r in await _repo.roles_by_ids(db, role_ids)}


async def apply_system_role_permissions(
    db: AsyncSession, org_id: uuid.UUID, role_code: str, permissions: dict[str, str]
) -> bool:
    """Superadmin push of DEFAULT_ROLES: overwrite one system role's matrix. Custom roles and ORG_OWNER untouched."""
    role = await _repo.get_role_by_code(db, org_id, role_code)
    if role is None or not role.is_system_role or role.role_code == "ORG_OWNER":
        return False
    role.permissions = effective_permissions(permissions, is_owner=False)
    await db.flush()
    return True
