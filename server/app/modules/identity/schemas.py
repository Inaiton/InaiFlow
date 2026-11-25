from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import EmailStr, Field

from app.core.schemas import InModel, OutModel


class MeOut(OutModel):
    id: uuid.UUID
    email: EmailStr
    full_name: str
    mobile: str | None
    professional_reg_no: str | None
    avatar_url: str | None
    signature_url: str | None
    is_email_verified: bool
    mfa_enabled: bool
    created_at: datetime


class SignupIn(InModel):
    full_name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(max_length=256)


class SignupOut(OutModel):
    email: EmailStr
    verification_required: bool


class VerifyEmailIn(InModel):
    email: EmailStr
    code: str = Field(min_length=4, max_length=12)


class EmailIn(InModel):
    email: EmailStr


class LoginIn(InModel):
    email: EmailStr
    password: str = Field(max_length=256)
    remember: bool = False


class TokenOut(OutModel):
    """Auth token envelope. NOTE: the contract also defines a documents ``TokenOut`` (template tokens) with
    the same name — reported in docs/plan/requests/contract.md; documents should use ``TemplateTokenOut``."""

    access_token: str
    token_type: str = "bearer"  # noqa: S105
    expires_in: int


class LoginOut(OutModel):
    status: Literal["OK", "MFA_REQUIRED"]
    token: TokenOut | None
    mfa_token: str | None
    user: MeOut | None


class MfaVerifyIn(InModel):
    mfa_token: str
    code: str = Field(min_length=6, max_length=20)


class LoginSuccessOut(OutModel):
    token: TokenOut
    user: MeOut


class PasswordResetIn(InModel):
    email: EmailStr
    code: str = Field(min_length=4, max_length=12)
    new_password: str = Field(max_length=256)


class MeUpdateIn(InModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    mobile: str | None = Field(default=None, max_length=20)
    professional_reg_no: str | None = Field(default=None, max_length=100)
    avatar_storage_key: str | None = None
    signature_storage_key: str | None = None


class MeFileUploadIn(InModel):
    purpose: Literal["AVATAR", "SIGNATURE"]
    content_type: str
    size_bytes: int


class PasswordChangeIn(InModel):
    current_password: str = Field(max_length=256)
    new_password: str = Field(max_length=256)


class MfaSetupOut(OutModel):
    secret: str
    otpauth_uri: str


class MfaCodeIn(InModel):
    code: str = Field(min_length=6, max_length=20)


class MfaDisableIn(InModel):
    password: str = Field(max_length=256)
    code: str = Field(min_length=6, max_length=20)


class RecoveryCodesOut(OutModel):
    recovery_codes: list[str]


class SessionOut(OutModel):
    id: uuid.UUID
    user_agent: str | None
    ip: str | None
    created_at: datetime
    last_used_at: datetime
    expires_at: datetime
    is_current: bool
