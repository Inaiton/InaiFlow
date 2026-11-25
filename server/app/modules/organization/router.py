"""Organization routes. This is the reference module for other streams (see server/README.md)."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.core.context import TenantContext
from app.core.deps import DB, CurrentUser, TenantDB, require
from app.core.pagination import Page
from app.core.schemas import AuditLogOut, OkOut, UploadTicket
from app.modules.organization import service
from app.modules.organization.schemas import (
    BillingOut,
    BranchIn,
    BranchOut,
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

NO_CONTENT = status.HTTP_204_NO_CONTENT
personal_router = APIRouter(tags=["me"])
router = APIRouter(tags=["organization"])

Member = Annotated[TenantContext, Depends(require(None))]
ProfileRead = Annotated[TenantContext, Depends(require("organization.profile", "READ"))]
ProfileFull = Annotated[TenantContext, Depends(require("organization.profile", "FULL"))]
MembersRead = Annotated[TenantContext, Depends(require("organization.members", "READ"))]
MembersFull = Annotated[TenantContext, Depends(require("organization.members", "FULL"))]
SecurityRead = Annotated[TenantContext, Depends(require("organization.security_policies", "READ"))]
SecurityFull = Annotated[TenantContext, Depends(require("organization.security_policies", "FULL"))]
AuditRead = Annotated[TenantContext, Depends(require("organization.audit_logs", "READ"))]
BillingRead = Annotated[TenantContext, Depends(require("organization.billing", "READ"))]


# ================================================================= personal space
@personal_router.get("/me/organizations", response_model=list[MyOrgOut])
async def my_organizations(user: CurrentUser, db: DB) -> list[MyOrgOut]:
    return await service.my_organizations(db, user)


@personal_router.get("/me/invitations", response_model=list[InvitationForMeOut])
async def my_invitations(user: CurrentUser, db: DB) -> list[InvitationForMeOut]:
    return await service.my_invitations(db, user)


@personal_router.post("/me/invitations/{invitation_id}/accept", response_model=MyOrgOut)
async def accept_invitation(invitation_id: uuid.UUID, user: CurrentUser, db: DB) -> MyOrgOut:
    return await service.accept_invitation(db, user, invitation_id)


@personal_router.post("/me/invitations/{invitation_id}/decline", status_code=NO_CONTENT)
async def decline_invitation(invitation_id: uuid.UUID, user: CurrentUser, db: DB) -> Response:
    await service.decline_invitation(db, user, invitation_id)
    return Response(status_code=NO_CONTENT)


@personal_router.get("/me/join-requests", response_model=list[MyJoinRequestOut])
async def my_join_requests(user: CurrentUser, db: DB) -> list[MyJoinRequestOut]:
    return await service.my_join_requests(db, user)


@personal_router.post("/me/join-requests", response_model=MyJoinRequestOut, status_code=status.HTTP_201_CREATED)
async def create_join_request(body: JoinRequestIn, user: CurrentUser, db: DB) -> MyJoinRequestOut:
    return await service.create_join_request(db, user, body)


@personal_router.delete("/me/join-requests/{request_id}", status_code=NO_CONTENT)
async def cancel_join_request(request_id: uuid.UUID, user: CurrentUser, db: DB) -> Response:
    await service.cancel_join_request(db, user, request_id)
    return Response(status_code=NO_CONTENT)


@personal_router.get("/organizations/check-slug", response_model=OkOut, tags=["organization"])
async def check_slug(user: CurrentUser, db: DB, slug: str = Query()) -> OkOut:
    return OkOut(ok=await service.check_slug(db, slug))


@personal_router.post("/organizations", response_model=MyOrgOut, status_code=status.HTTP_201_CREATED,
                      tags=["organization"])  # fmt: skip
async def create_organization(body: OrgCreateIn, user: CurrentUser, db: DB) -> MyOrgOut:
    return await service.create_organization(db, user, body)


# ================================================================= tenant
@router.get("/org/context", response_model=OrgContextOut)
async def org_context(ctx: Member, db: TenantDB) -> OrgContextOut:
    return await service.org_context(db, ctx)


@router.get("/organization/profile", response_model=OrgOut)
async def get_profile(ctx: ProfileRead, db: TenantDB) -> OrgOut:
    return await service.get_profile(db, ctx)


@router.patch("/organization/profile", response_model=OrgOut)
async def update_profile(body: OrgUpdateIn, ctx: ProfileFull, db: TenantDB) -> OrgOut:
    return await service.update_profile(db, ctx, body)


@router.post("/organization/files/upload-url", response_model=UploadTicket)
async def org_upload_url(body: OrgFileUploadIn, ctx: ProfileFull) -> UploadTicket:
    return await service.org_upload_url(ctx, body)


@router.get("/organization/branches", response_model=list[BranchOut])
async def list_branches(ctx: ProfileRead, db: TenantDB) -> list[BranchOut]:
    return await service.list_branches(db, ctx)


@router.post("/organization/branches", response_model=BranchOut, status_code=status.HTTP_201_CREATED)
async def create_branch(body: BranchIn, ctx: ProfileFull, db: TenantDB) -> BranchOut:
    return await service.create_branch(db, ctx, body)


@router.patch("/organization/branches/{branch_id}", response_model=BranchOut)
async def update_branch(branch_id: uuid.UUID, body: BranchIn, ctx: ProfileFull, db: TenantDB) -> BranchOut:
    return await service.update_branch(db, ctx, branch_id, body)


@router.delete("/organization/branches/{branch_id}", status_code=NO_CONTENT)
async def delete_branch(branch_id: uuid.UUID, ctx: ProfileFull, db: TenantDB) -> Response:
    await service.delete_branch(db, ctx, branch_id)
    return Response(status_code=NO_CONTENT)


@router.get("/organization/members", response_model=list[MemberOut])
async def list_members(ctx: MembersRead, db: TenantDB, q: str | None = None,
                       status: str | None = None) -> list[MemberOut]:  # fmt: skip
    return await service.list_members(db, ctx, q, status)


@router.patch("/organization/members/{membership_id}", response_model=MemberOut)
async def update_member(membership_id: uuid.UUID, body: MemberUpdateIn, ctx: MembersFull, db: TenantDB) -> MemberOut:
    return await service.update_member(db, ctx, membership_id, body)


@router.delete("/organization/members/{membership_id}", status_code=NO_CONTENT)
async def remove_member(membership_id: uuid.UUID, ctx: MembersFull, db: TenantDB) -> Response:
    await service.remove_member(db, ctx, membership_id)
    return Response(status_code=NO_CONTENT)


@router.post("/organization/transfer-ownership", status_code=NO_CONTENT)
async def transfer_ownership(body: TransferOwnershipIn, ctx: MembersFull, db: TenantDB) -> Response:
    await service.transfer_ownership(db, ctx, body)
    return Response(status_code=NO_CONTENT)


@router.get("/organization/invitations", response_model=list[InvitationOut])
async def list_invitations(ctx: MembersRead, db: TenantDB, status: str | None = None) -> list[InvitationOut]:
    return await service.list_invitations(db, ctx, status)


@router.post("/organization/invitations", response_model=InvitationOut, status_code=status.HTTP_201_CREATED)
async def create_invitation(body: InvitationIn, ctx: MembersFull, db: TenantDB) -> InvitationOut:
    return await service.create_invitation(db, ctx, body)


@router.post("/organization/invitations/{invitation_id}/resend", status_code=NO_CONTENT)
async def resend_invitation(invitation_id: uuid.UUID, ctx: MembersFull, db: TenantDB) -> Response:
    await service.resend_invitation(db, ctx, invitation_id)
    return Response(status_code=NO_CONTENT)


@router.delete("/organization/invitations/{invitation_id}", status_code=NO_CONTENT)
async def cancel_invitation(invitation_id: uuid.UUID, ctx: MembersFull, db: TenantDB) -> Response:
    await service.cancel_invitation(db, ctx, invitation_id)
    return Response(status_code=NO_CONTENT)


@router.get("/organization/join-requests", response_model=list[JoinRequestOut])
async def list_join_requests(ctx: MembersRead, db: TenantDB, status: str | None = None) -> list[JoinRequestOut]:
    return await service.list_join_requests(db, ctx, status)


@router.post("/organization/join-requests/{request_id}/approve", response_model=MemberOut)
async def approve_join_request(request_id: uuid.UUID, body: JoinDecisionIn, ctx: MembersFull,
                               db: TenantDB) -> MemberOut:  # fmt: skip
    return await service.approve_join_request(db, ctx, request_id, body)


@router.post("/organization/join-requests/{request_id}/reject", status_code=NO_CONTENT)
async def reject_join_request(request_id: uuid.UUID, ctx: MembersFull, db: TenantDB) -> Response:
    await service.reject_join_request(db, ctx, request_id)
    return Response(status_code=NO_CONTENT)


@router.get("/organization/security", response_model=SecuritySettings)
async def get_security(ctx: SecurityRead, db: TenantDB) -> SecuritySettings:
    return await service.get_security(db, ctx)


@router.put("/organization/security", response_model=SecuritySettings)
async def put_security(body: SecuritySettings, ctx: SecurityFull, db: TenantDB) -> SecuritySettings:
    return await service.put_security(db, ctx, body)


@router.get("/organization/audit-logs", response_model=Page[AuditLogOut])
async def audit_logs(
    ctx: AuditRead, db: TenantDB, module: str | None = None, action: str | None = None,
    entity_type: str | None = None, entity_id: uuid.UUID | None = None, user_id: uuid.UUID | None = None,
    date_from: date | None = None, date_to: date | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50, offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[AuditLogOut]:  # fmt: skip
    return await service.audit_logs(db, ctx, limit=limit, offset=offset, module=module, action=action,
                                    entity_type=entity_type, entity_id=entity_id, user_id=user_id,
                                    date_from=date_from, date_to=date_to)  # fmt: skip


@router.get("/organization/billing", response_model=BillingOut)
async def billing(ctx: BillingRead, db: TenantDB) -> BillingOut:
    return await service.billing(db, ctx)
