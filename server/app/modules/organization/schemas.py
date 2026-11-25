from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import EmailStr, Field

from app.core.money import DecimalStr
from app.core.schemas import InModel, OutModel

Level = Literal["NONE", "READ", "WRITE", "FULL"]
SLUG_PATTERN = r"^[a-z0-9-]{3,50}$"
GST_REG_TYPES = Literal["REGULAR", "COMPOSITION", "UNREGISTERED", "SEZ"]


# ---------------------------------------------------------------- personal space
class MyOrgOut(OutModel):
    org_id: uuid.UUID
    legal_name: str
    mailing_name: str | None
    workspace_slug: str
    public_join_code: str
    logo_url: str | None
    role_id: uuid.UUID
    role_code: str
    role_name: str
    is_external: bool
    membership_status: str
    access_expires_at: datetime | None
    org_status: str


class InvitationForMeOut(OutModel):
    id: uuid.UUID
    org_id: uuid.UUID
    org_name: str
    role_name: str
    invited_by_name: str | None
    access_expires_at: datetime | None
    expires_at: datetime
    created_at: datetime


class JoinRequestIn(InModel):
    join_code: str = Field(min_length=4, max_length=20)
    message: str | None = Field(default=None, max_length=1000)


class MyJoinRequestOut(OutModel):
    id: uuid.UUID
    org_name: str
    public_join_code: str
    status: str
    message: str | None
    created_at: datetime


class OrgCreateIn(InModel):
    legal_name: str = Field(min_length=2, max_length=255)
    mailing_name: str | None = Field(default=None, max_length=255)
    workspace_slug: str = Field(pattern=SLUG_PATTERN)
    address_line1: str = Field(min_length=1)
    address_line2: str | None = None
    city: str = Field(min_length=1, max_length=100)
    state_code: str = Field(pattern=r"^\d{2}$")
    pincode: str = Field(min_length=3, max_length=15)
    country: str = "India"
    fy_begins_from: date
    books_beginning_from: date
    contact_email: EmailStr
    contact_phone: str = Field(min_length=5, max_length=30)
    gst_reg_type: GST_REG_TYPES
    gstin: str | None = Field(default=None, pattern=r"^\d{2}[A-Z0-9]{13}$")
    pan: str | None = Field(default=None, pattern=r"^[A-Z]{5}\d{4}[A-Z]$")
    tan: str | None = Field(default=None, pattern=r"^[A-Z]{4}\d{5}[A-Z]$")
    cin_or_udyam: str | None = Field(default=None, max_length=50)
    epf_code: str | None = Field(default=None, max_length=50)
    esic_code: str | None = Field(default=None, max_length=50)
    industry_type: str = Field(min_length=2, max_length=100)
    iso_standard: str | None = "ISO_9001_2015"


# ---------------------------------------------------------------- tenant
class FyOut(OutModel):
    label: str
    start: date
    end: date


class ImpersonationInfo(OutModel):
    admin_name: str
    mode: str
    expires_at: datetime


class OrgContextOut(OutModel):
    org_id: uuid.UUID
    legal_name: str
    mailing_name: str | None
    workspace_slug: str
    logo_url: str | None
    state_code: str
    base_currency_code: str
    base_currency_symbol: str
    role_code: str
    role_name: str
    is_external: bool
    is_owner: bool
    permissions: dict[str, Level]
    enabled_modules: dict[str, bool]
    current_fy: FyOut
    books_beginning_from: date
    impersonation: ImpersonationInfo | None


class OrgOut(OutModel):
    id: uuid.UUID
    workspace_slug: str
    public_join_code: str
    legal_name: str
    mailing_name: str | None
    address_line1: str
    address_line2: str | None
    city: str
    state_code: str
    state_name: str
    pincode: str
    country: str
    base_currency_code: str
    base_currency_symbol: str
    fy_begins_from: date
    books_beginning_from: date
    contact_email: str
    contact_phone: str
    gst_reg_type: str
    gstin: str | None
    pan: str | None
    tan: str | None
    cin_or_udyam: str | None
    epf_code: str | None
    esic_code: str | None
    industry_type: str
    iso_standard: str | None
    logo_url: str | None
    stamp_url: str | None
    org_status: str
    created_at: datetime


class OrgUpdateIn(InModel):
    legal_name: str | None = Field(default=None, min_length=2, max_length=255)
    mailing_name: str | None = None
    address_line1: str | None = Field(default=None, min_length=1)
    address_line2: str | None = None
    city: str | None = Field(default=None, min_length=1, max_length=100)
    state_code: str | None = Field(default=None, pattern=r"^\d{2}$")
    pincode: str | None = Field(default=None, min_length=3, max_length=15)
    contact_email: EmailStr | None = None
    contact_phone: str | None = Field(default=None, min_length=5, max_length=30)
    gst_reg_type: GST_REG_TYPES | None = None
    gstin: str | None = Field(default=None, pattern=r"^\d{2}[A-Z0-9]{13}$")
    pan: str | None = Field(default=None, pattern=r"^[A-Z]{5}\d{4}[A-Z]$")
    tan: str | None = Field(default=None, pattern=r"^[A-Z]{4}\d{5}[A-Z]$")
    cin_or_udyam: str | None = None
    epf_code: str | None = None
    esic_code: str | None = None
    industry_type: str | None = Field(default=None, min_length=2, max_length=100)
    iso_standard: str | None = None
    logo_storage_key: str | None = None
    stamp_storage_key: str | None = None


class OrgFileUploadIn(InModel):
    purpose: Literal["LOGO", "STAMP"]
    content_type: str
    size_bytes: int


class BranchIn(InModel):
    name: str = Field(min_length=1, max_length=200)
    address: str | None = None
    state_code: str | None = Field(default=None, pattern=r"^\d{2}$")
    gstin: str | None = Field(default=None, pattern=r"^\d{2}[A-Z0-9]{13}$")
    is_head_office: bool = False


class BranchOut(OutModel):
    id: uuid.UUID
    name: str
    address: str | None
    state_code: str | None
    gstin: str | None
    is_head_office: bool


class MemberOut(OutModel):
    membership_id: uuid.UUID
    user_id: uuid.UUID
    full_name: str
    email: str
    role_id: uuid.UUID
    role_code: str
    role_name: str
    is_external: bool
    is_owner: bool
    status: str
    access_expires_at: datetime | None
    joined_at: datetime
    mfa_enabled: bool


class MemberUpdateIn(InModel):
    role_id: uuid.UUID | None = None
    access_expires_at: datetime | None = None
    status: Literal["ACTIVE", "SUSPENDED"] | None = None


class AclGrantIn(InModel):
    resource_type: Literal["STOCK_ITEM", "PERIOD_RUN", "DOC_FOLDER", "GODOWN"]
    resource_id: uuid.UUID
    access_level: Level


class InvitationIn(InModel):
    email: EmailStr
    role_id: uuid.UUID
    access_expires_at: datetime | None = None
    acl_grants: list[AclGrantIn] = Field(default_factory=list)


class InvitationOut(OutModel):
    id: uuid.UUID
    email: str
    role_id: uuid.UUID
    role_name: str
    status: str
    access_expires_at: datetime | None
    expires_at: datetime
    created_by_name: str | None
    created_at: datetime


class JoinRequestOut(OutModel):
    id: uuid.UUID
    user_id: uuid.UUID
    full_name: str
    email: str
    is_email_verified: bool
    professional_reg_no: str | None
    message: str | None
    status: str
    created_at: datetime


class JoinDecisionIn(InModel):
    role_id: uuid.UUID
    access_expires_at: datetime | None = None


class TransferOwnershipIn(InModel):
    membership_id: uuid.UUID
    password: str


class SecuritySettings(InModel):
    enforce_2fa_external: bool
    enforce_2fa_all: bool
    session_timeout_mins: int = Field(ge=5, le=60 * 24 * 30)
    voucher_approval_threshold: DecimalStr | None
    require_reviewer_for_iso_docs: bool


class BillingOut(OutModel):
    plan_code: str | None
    plan_name: str | None
    org_status: str
    trial_ends_at: datetime | None
    internal_seats_used: int
    internal_seats_max: int
    external_seats_used: int
    external_seats_max: int
    storage_used_bytes: int
    storage_max_gb: int
    enabled_modules: dict[str, bool]
