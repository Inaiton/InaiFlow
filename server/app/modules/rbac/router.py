from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.core.context import TenantContext
from app.core.deps import TenantDB, require
from app.modules.rbac import service
from app.modules.rbac.schemas import AclIn, AclOut, RoleIn, RoleOut, RoleUpdateIn

router = APIRouter(prefix="/organization", tags=["organization"])
RbacRead = Annotated[TenantContext, Depends(require("organization.roles_rbac", "READ"))]
RbacFull = Annotated[TenantContext, Depends(require("organization.roles_rbac", "FULL"))]


@router.get("/roles", response_model=list[RoleOut])
async def list_roles(ctx: RbacRead, db: TenantDB) -> list[RoleOut]:
    return await service.list_roles(db, ctx)


@router.post("/roles", response_model=RoleOut, status_code=status.HTTP_201_CREATED)
async def create_role(body: RoleIn, ctx: RbacFull, db: TenantDB) -> RoleOut:
    return await service.create_role(db, ctx, body)


@router.patch("/roles/{role_id}", response_model=RoleOut)
async def update_role(role_id: uuid.UUID, body: RoleUpdateIn, ctx: RbacFull, db: TenantDB) -> RoleOut:
    return await service.update_role(db, ctx, role_id, body)


@router.delete("/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(role_id: uuid.UUID, ctx: RbacFull, db: TenantDB) -> Response:
    await service.delete_role(db, ctx, role_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/acl", response_model=list[AclOut])
async def list_acl(
    ctx: RbacRead, db: TenantDB, subject_type: str | None = None, subject_id: uuid.UUID | None = None,
    resource_type: str | None = None,
) -> list[AclOut]:  # fmt: skip
    return await service.list_acl(db, ctx, subject_type, subject_id, resource_type)


@router.put("/acl", response_model=AclOut)
async def put_acl(body: AclIn, ctx: RbacFull, db: TenantDB) -> AclOut:
    return await service.put_acl(db, ctx, body)


@router.delete("/acl/{acl_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_acl(acl_id: uuid.UUID, ctx: RbacFull, db: TenantDB) -> Response:
    await service.delete_acl(db, ctx, acl_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
