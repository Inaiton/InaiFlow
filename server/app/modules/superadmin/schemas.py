"""Superadmin DTOs — named exactly like the contract models (docs/api/contract.api, section superadmin)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Annotated, Any, Literal

from pydantic import EmailStr, Field, field_validator

from app.core.money import DecimalStr
from app.core.schemas import InModel, OutModel
from app.modules.identity.interface import TokenOut

AdminRole = Literal["SUPERADMIN", "SUPPORT_ADMIN", "BILLING_ADMIN"]
AdminLoginStatus = Literal["MFA_REQUIRED", "MFA_SETUP_REQUIRED", "PASSWORD_CHANGE_REQUIRED"]
LifecycleAction = Literal["ACTIVATE", "SUSPEND", "ARCHIVE", "EXTEND_TRIAL"]
ImpersonationMode = Literal["READ_ONLY", "FULL_SUPPORT"]
UserAction = Literal["SUSPEND", "UNSUSPEND", "RESET_MFA", "VERIFY_EMAIL", "REVOKE_SESSIONS"]
InvoiceStatus = Literal["DUE", "PAID", "VOID"]
OrgStatus = Literal["ACTIVE", "TRIAL", "SUSPENDED", "ARCHIVED"]

Reason = Annotated[str, Field(min_length=3, max_length=1000)]


# ---------------------------------------------------------------- auth
class AdminLoginIn(InModel):
    email: EmailStr
    password: str = Field(max_length=256)


class AdminLoginOut(OutModel):
    status: AdminLoginStatus
    mfa_token: str
    otpauth_uri: str | None


class AdminMfaVerifyIn(InModel):
    mfa_token: str
    code: str = Field(max_length=32)
    new_password: str | None = None


class AdminMeOut(OutModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: AdminRole
    mfa_enabled: bool
    last_login_at: datetime | None


class AdminLoginSuccessOut(OutModel):
    token: TokenOut
    admin: AdminMeOut


# ---------------------------------------------------------------- organizations
class SignupPoint(OutModel):
    date: date
    count: int


class AdminOrgSummary(OutModel):
    id: uuid.UUID
    legal_name: str
    workspace_slug: str
    public_join_code: str
    gstin: str | None
    industry_type: str
    state_code: str
    org_status: str
    plan_code: str | None
    member_count: int
    owner_email: str
    created_at: datetime
    trial_ends_at: datetime | None


class AdminOrgDetail(AdminOrgSummary):
    owner_user_id: uuid.UUID
    owner_name: str
    external_count: int
    storage_used_bytes: int
    quota_overrides: Any
    plan_id: uuid.UUID | None
    contact_email: str
    contact_phone: str
    city: str
    voucher_count: int
    run_count: int


class AdminDashboardOut(OutModel):
    orgs_total: int
    orgs_active: int
    orgs_trial: int
    orgs_suspended: int
    users_total: int
    mrr_inr: DecimalStr
    active_runs: int
    vouchers_today: int
    storage_bytes: int
    irp_health: str
    signups_series: list[SignupPoint]
    recent_orgs: list[AdminOrgSummary]


class LifecycleIn(InModel):
    action: LifecycleAction
    reason: Reason
    trial_days: int | None = Field(default=None, ge=1, le=365)


class PlanChangeIn(InModel):
    plan_id: uuid.UUID
    quota_overrides: dict[str, Any] | None = None
    reason: Reason


class TransferOwnerIn(InModel):
    new_owner_user_id: uuid.UUID
    reason: Reason


class ImpersonateIn(InModel):
    mode: ImpersonationMode
    ticket_reference: str = Field(min_length=2, max_length=100)
    reason: Reason


class ImpersonateOut(OutModel):
    session_id: uuid.UUID
    token: str
    expires_at: datetime
    launch_url: str


class AdminOrgMemberOut(OutModel):
    user_id: uuid.UUID
    full_name: str
    email: str
    role_code: str
    status: str


# ---------------------------------------------------------------- users
class AdminUserSummary(OutModel):
    id: uuid.UUID
    email: str
    full_name: str
    is_email_verified: bool
    mfa_enabled: bool
    is_suspended: bool
    org_count: int
    last_login_at: datetime | None
    created_at: datetime


class AdminMembershipOut(OutModel):
    org_id: uuid.UUID
    org_name: str
    role_code: str
    status: str
    access_expires_at: datetime | None


class AdminUserDetail(AdminUserSummary):
    mobile: str | None
    professional_reg_no: str | None
    memberships: list[AdminMembershipOut]
    active_sessions: int


class UserActionIn(InModel):
    action: UserAction
    reason: Reason


# ---------------------------------------------------------------- configs
class ConfigOut(OutModel):
    id: uuid.UUID
    config_category: str
    config_key: str
    display_name: str
    payload: Any
    version: int
    is_active: bool
    effective_from: date | None
    updated_by_name: str | None
    updated_at: datetime


class ConfigIn(InModel):
    config_category: str = Field(min_length=2, max_length=100, pattern=r"^[A-Z][A-Z0-9_]*$")
    config_key: str = Field(min_length=1, max_length=150, pattern=r"^[A-Za-z0-9_.\-]+$")
    display_name: str = Field(min_length=1, max_length=255)
    payload: dict[str, Any]
    effective_from: date | None = None
    reason: Reason


class ConfigUpdateIn(InModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=255)
    payload: dict[str, Any]
    is_active: bool | None = None
    effective_from: date | None = None
    reason: Reason


class ConfigVersionOut(OutModel):
    version: int
    payload: Any
    effective_from: date | None
    change_reason: str | None
    created_by_name: str | None
    created_at: datetime


class ConfigPushIn(InModel):
    org_ids: list[uuid.UUID] | None = Field(default=None, max_length=1000)
    all_orgs: bool | None = None
    reason: Reason


class ConfigPushOut(OutModel):
    orgs_updated: int
    orgs_skipped: int


# ---------------------------------------------------------------- plans & billing
ModuleFlags = dict[str, bool]


class PlanOut(OutModel):
    id: uuid.UUID
    plan_code: str
    name: str
    monthly_price_inr: DecimalStr
    annual_price_inr: DecimalStr
    max_internal_seats: int
    max_external_collaborators: int
    max_storage_gb: int
    enabled_modules: ModuleFlags
    is_active: bool
    org_count: int
    created_at: datetime


class PlanIn(InModel):
    plan_code: str = Field(min_length=2, max_length=50, pattern=r"^[A-Z][A-Z0-9_]*$")
    name: str = Field(min_length=1, max_length=100)
    monthly_price_inr: DecimalStr
    annual_price_inr: DecimalStr
    max_internal_seats: int = Field(ge=0, le=100000)
    max_external_collaborators: int = Field(ge=0, le=100000)
    max_storage_gb: int = Field(ge=0, le=1000000)
    enabled_modules: ModuleFlags
    is_active: bool | None = None
    reason: Reason


class PlanUpdateIn(InModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    monthly_price_inr: DecimalStr | None = None
    annual_price_inr: DecimalStr | None = None
    max_internal_seats: int | None = Field(default=None, ge=0, le=100000)
    max_external_collaborators: int | None = Field(default=None, ge=0, le=100000)
    max_storage_gb: int | None = Field(default=None, ge=0, le=1000000)
    enabled_modules: ModuleFlags | None = None
    is_active: bool | None = None
    reason: Reason


class SubscriptionInvoiceOut(OutModel):
    id: uuid.UUID
    org_id: uuid.UUID
    org_name: str
    invoice_number: str
    period_start: date
    period_end: date
    amount_inr: DecimalStr
    status: InvoiceStatus
    paid_at: datetime | None
    created_at: datetime


class SubscriptionInvoiceIn(InModel):
    org_id: uuid.UUID
    period_start: date
    period_end: date
    amount_inr: DecimalStr
    reason: Reason


class InvoiceStatusIn(InModel):
    status: InvoiceStatus
    reason: Reason


# ---------------------------------------------------------------- audit, admins, system
class PlatformAuditOut(OutModel):
    id: uuid.UUID
    admin_id: uuid.UUID | None
    admin_email: str | None
    action: str
    target_type: str
    target_id: uuid.UUID | None
    before_state: Any | None
    after_state: Any | None
    ip_address: str | None
    created_at: datetime


class AdminAccountOut(OutModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: AdminRole
    is_active: bool
    mfa_enabled: bool
    last_login_at: datetime | None
    created_at: datetime


class AdminAccountIn(InModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=255)
    role: AdminRole

    @field_validator("email")
    @classmethod
    def _lower(cls, v: str) -> str:
        return v.strip().lower()


class AdminAccountCreatedOut(OutModel):
    admin: AdminAccountOut
    temporary_password: str


class AdminAccountUpdateIn(InModel):
    role: AdminRole | None = None
    is_active: bool | None = None
    reason: Reason


class SystemHealthOut(OutModel):
    db: str
    storage: str
    email: str
    tax_gateway: str
    version: str
    environment: str


class TemplateTokenOut(OutModel):
    token: str
    label: str
    group: str
    sample: str
