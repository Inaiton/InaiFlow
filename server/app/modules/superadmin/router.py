"""/api/v1/admin/* — platform admin console API (contract section "superadmin").

Every route checks ``ADMIN_IP_ALLOWLIST`` (public auth routes via ``check_admin_ip``, the rest via
``require_admin`` -> ``get_admin_principal``).
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request, Response, status

from app.core.config import get_settings
from app.core.context import AdminPrincipal
from app.core.deps import DB, check_admin_ip, require_admin, user_agent
from app.core.errors import ForbiddenError
from app.core.pagination import Page, Paging
from app.modules.superadmin import service, service_auth, service_billing, service_configs
from app.modules.superadmin.schemas import (
    AdminAccountCreatedOut,
    AdminAccountIn,
    AdminAccountOut,
    AdminAccountUpdateIn,
    AdminDashboardOut,
    AdminLoginIn,
    AdminLoginOut,
    AdminLoginSuccessOut,
    AdminMeOut,
    AdminMfaVerifyIn,
    AdminOrgDetail,
    AdminOrgMemberOut,
    AdminOrgSummary,
    AdminUserDetail,
    AdminUserSummary,
    ConfigIn,
    ConfigOut,
    ConfigPushIn,
    ConfigPushOut,
    ConfigUpdateIn,
    ConfigVersionOut,
    ImpersonateIn,
    ImpersonateOut,
    InvoiceStatusIn,
    LifecycleIn,
    PlanChangeIn,
    PlanIn,
    PlanOut,
    PlanUpdateIn,
    PlatformAuditOut,
    SubscriptionInvoiceIn,
    SubscriptionInvoiceOut,
    SystemHealthOut,
    TemplateTokenOut,
    TransferOwnerIn,
    UserActionIn,
)

router = APIRouter(prefix="/admin", tags=["superadmin"])

REFRESH_COOKIE = "if_art"
COOKIE_PATH = "/api/v1/admin/auth"
NO_CONTENT = status.HTTP_204_NO_CONTENT

Any_ = Annotated[AdminPrincipal, Depends(require_admin())]
Super = Annotated[AdminPrincipal, Depends(require_admin("SUPERADMIN"))]
Support = Annotated[AdminPrincipal, Depends(require_admin("SUPERADMIN", "SUPPORT_ADMIN"))]
Billing = Annotated[AdminPrincipal, Depends(require_admin("SUPERADMIN", "BILLING_ADMIN"))]


def _set_refresh(response: Response, raw: str) -> None:
    response.set_cookie(REFRESH_COOKIE, raw, max_age=int(service_auth.ADMIN_REFRESH_TTL.total_seconds()),
                        path=COOKIE_PATH, httponly=True, secure=get_settings().cookie_secure, samesite="strict")  # fmt: skip


# ---------------------------------------------------------------- auth (public)
@router.post("/auth/login", response_model=AdminLoginOut)
async def login(body: AdminLoginIn, request: Request, db: DB) -> AdminLoginOut:
    return await service_auth.login(db, body, check_admin_ip(request))


@router.post("/auth/mfa/verify", response_model=AdminLoginSuccessOut)
async def mfa_verify(body: AdminMfaVerifyIn, request: Request, response: Response, db: DB) -> AdminLoginSuccessOut:
    ip = check_admin_ip(request)
    issued = await service_auth.verify_mfa(db, body.mfa_token, body.code, body.new_password, ip, user_agent(request))
    _set_refresh(response, issued.refresh_token)
    return issued.body


@router.post("/auth/refresh", response_model=AdminLoginSuccessOut)
async def refresh(
    request: Request, response: Response, db: DB,
    x_requested_with: Annotated[str | None, Header(alias="X-Requested-With")] = None,
) -> AdminLoginSuccessOut:  # fmt: skip
    ip = check_admin_ip(request)
    if x_requested_with != "inaiflow":
        raise ForbiddenError("Missing X-Requested-With: inaiflow")
    issued = await service_auth.refresh(db, request.cookies.get(REFRESH_COOKIE), ip, user_agent(request))
    _set_refresh(response, issued.refresh_token)
    return issued.body


@router.post("/auth/logout", status_code=NO_CONTENT)
async def logout(request: Request, db: DB) -> Response:
    check_admin_ip(request)
    await service_auth.logout(db, request.cookies.get(REFRESH_COOKIE))
    response = Response(status_code=NO_CONTENT)
    response.delete_cookie(REFRESH_COOKIE, path=COOKIE_PATH, httponly=True, secure=get_settings().cookie_secure,
                           samesite="strict")  # fmt: skip
    return response


@router.get("/me", response_model=AdminMeOut)
async def me(admin: Any_, db: DB) -> AdminMeOut:
    return await service_auth.get_me(db, admin)


# ---------------------------------------------------------------- dashboard & organizations
@router.get("/dashboard", response_model=AdminDashboardOut)
async def dashboard(admin: Any_, db: DB) -> AdminDashboardOut:
    return await service.dashboard(db)


@router.get("/organizations", response_model=Page[AdminOrgSummary])
async def list_orgs(
    admin: Any_, db: DB, page: Paging, q: str | None = None, status: str | None = None,
    plan_code: str | None = None, industry: str | None = None,
) -> Page[AdminOrgSummary]:  # fmt: skip
    return await service.list_orgs(db, q=q, status=status, plan_code=plan_code, industry=industry, page=page)


@router.get("/organizations/{org_id}", response_model=AdminOrgDetail)
async def org_detail(org_id: uuid.UUID, admin: Any_, db: DB) -> AdminOrgDetail:
    return await service.org_detail(db, org_id)


@router.post("/organizations/{org_id}/lifecycle", response_model=AdminOrgDetail)
async def lifecycle(org_id: uuid.UUID, body: LifecycleIn, admin: Support, db: DB) -> AdminOrgDetail:
    return await service.lifecycle(db, admin, org_id, body)


@router.patch("/organizations/{org_id}/plan", response_model=AdminOrgDetail)
async def change_plan(org_id: uuid.UUID, body: PlanChangeIn, admin: Billing, db: DB) -> AdminOrgDetail:
    return await service.change_plan(db, admin, org_id, body)


@router.post("/organizations/{org_id}/transfer-owner", response_model=AdminOrgDetail)
async def transfer_owner(org_id: uuid.UUID, body: TransferOwnerIn, admin: Super, db: DB) -> AdminOrgDetail:
    return await service.transfer_owner(db, admin, org_id, body)


@router.post("/organizations/{org_id}/impersonate", response_model=ImpersonateOut, status_code=201)
async def impersonate(org_id: uuid.UUID, body: ImpersonateIn, admin: Support, db: DB) -> ImpersonateOut:
    return await service.impersonate(db, admin, org_id, body)


@router.get("/organizations/{org_id}/members", response_model=list[AdminOrgMemberOut])
async def org_members(org_id: uuid.UUID, admin: Support, db: DB) -> list[AdminOrgMemberOut]:
    return await service.org_members(db, org_id)


# ---------------------------------------------------------------- users
@router.get("/users", response_model=Page[AdminUserSummary])
async def list_users(admin: Support, db: DB, page: Paging, q: str | None = None,
                     suspended: bool | None = None) -> Page[AdminUserSummary]:  # fmt: skip
    return await service.list_users(db, q=q, suspended=suspended, page=page)


@router.get("/users/{user_id}", response_model=AdminUserDetail)
async def user_detail(user_id: uuid.UUID, admin: Support, db: DB) -> AdminUserDetail:
    return await service.user_detail(db, user_id)


@router.post("/users/{user_id}/actions", response_model=AdminUserDetail)
async def user_action(user_id: uuid.UUID, body: UserActionIn, admin: Support, db: DB) -> AdminUserDetail:
    return await service.user_action(db, admin, user_id, body)


# ---------------------------------------------------------------- configs
@router.get("/configs", response_model=list[ConfigOut])
async def list_configs(admin: Any_, db: DB, category: str | None = None) -> list[ConfigOut]:
    return await service_configs.list_configs(db, category)


@router.post("/configs", response_model=ConfigOut, status_code=201)
async def create_config(body: ConfigIn, admin: Super, db: DB) -> ConfigOut:
    return await service_configs.create_config(db, admin, body)


@router.get("/configs/{config_id}", response_model=ConfigOut)
async def get_config(config_id: uuid.UUID, admin: Any_, db: DB) -> ConfigOut:
    return await service_configs.get_config(db, config_id)


@router.put("/configs/{config_id}", response_model=ConfigOut)
async def update_config(config_id: uuid.UUID, body: ConfigUpdateIn, admin: Super, db: DB) -> ConfigOut:
    return await service_configs.update_config(db, admin, config_id, body)


@router.get("/configs/{config_id}/history", response_model=list[ConfigVersionOut])
async def config_history(config_id: uuid.UUID, admin: Any_, db: DB) -> list[ConfigVersionOut]:
    return await service_configs.history(db, config_id)


@router.post("/configs/{config_id}/push", response_model=ConfigPushOut)
async def push_config(config_id: uuid.UUID, body: ConfigPushIn, admin: Super, db: DB) -> ConfigPushOut:
    return await service_configs.push(db, admin, config_id, body)


# ---------------------------------------------------------------- plans & billing
@router.get("/plans", response_model=list[PlanOut])
async def list_plans(admin: Any_, db: DB) -> list[PlanOut]:
    return await service_billing.list_plans(db)


@router.post("/plans", response_model=PlanOut, status_code=201)
async def create_plan(body: PlanIn, admin: Billing, db: DB) -> PlanOut:
    return await service_billing.create_plan(db, admin, body)


@router.patch("/plans/{plan_id}", response_model=PlanOut)
async def update_plan(plan_id: uuid.UUID, body: PlanUpdateIn, admin: Billing, db: DB) -> PlanOut:
    return await service_billing.update_plan(db, admin, plan_id, body)


@router.get("/billing/invoices", response_model=Page[SubscriptionInvoiceOut])
async def list_invoices(admin: Billing, db: DB, page: Paging, org_id: uuid.UUID | None = None,
                        status: str | None = None) -> Page[SubscriptionInvoiceOut]:  # fmt: skip
    return await service_billing.list_invoices(db, org_id=org_id, status=status, page=page)


@router.post("/billing/invoices", response_model=SubscriptionInvoiceOut, status_code=201)
async def create_invoice(body: SubscriptionInvoiceIn, admin: Billing, db: DB) -> SubscriptionInvoiceOut:
    return await service_billing.create_invoice(db, admin, body)


@router.patch("/billing/invoices/{invoice_id}", response_model=SubscriptionInvoiceOut)
async def invoice_status(
    invoice_id: uuid.UUID, body: InvoiceStatusIn, admin: Billing, db: DB
) -> SubscriptionInvoiceOut:
    return await service_billing.set_invoice_status(db, admin, invoice_id, body)


# ---------------------------------------------------------------- audit, admins, meta, system
@router.get("/audit-logs", response_model=Page[PlatformAuditOut])
async def audit_logs(
    admin: Any_, db: DB, page: Paging, action: str | None = None, target_type: str | None = None,
    admin_id: uuid.UUID | None = None, date_from: date | None = None, date_to: date | None = None,
) -> Page[PlatformAuditOut]:  # fmt: skip
    return await service_billing.audit_logs(db, page, action=action, target_type=target_type, admin_id=admin_id,
                                            date_from=date_from, date_to=date_to)  # fmt: skip


@router.get("/admins", response_model=list[AdminAccountOut])
async def list_admins(admin: Super, db: DB) -> list[AdminAccountOut]:
    return await service_billing.list_admins(db)


@router.post("/admins", response_model=AdminAccountCreatedOut, status_code=201)
async def create_admin(body: AdminAccountIn, admin: Super, db: DB) -> AdminAccountCreatedOut:
    return await service_billing.create_admin(db, admin, body)


@router.patch("/admins/{admin_id}", response_model=AdminAccountOut)
async def update_admin(admin_id: uuid.UUID, body: AdminAccountUpdateIn, admin: Super, db: DB) -> AdminAccountOut:
    return await service_billing.update_admin(db, admin, admin_id, body)


@router.get("/meta/template-tokens", response_model=list[TemplateTokenOut])
async def template_tokens(admin: Any_) -> list[TemplateTokenOut]:
    return service.template_tokens()


@router.get("/system/health", response_model=SystemHealthOut)
async def system_health(admin: Any_, db: DB) -> SystemHealthOut:
    return await service.system_health(db)
