"""Platform-admin authentication (plan §3.3): password -> mandatory TOTP (enrolled on first login) -> tokens.

State machine of ``POST /admin/auth/login`` (always a challenge, never tokens):
* ``must_change_password``      -> PASSWORD_CHANGE_REQUIRED (+ ``otpauth_uri`` while MFA is not yet enrolled)
* MFA not enrolled              -> MFA_SETUP_REQUIRED with ``otpauth_uri`` (secret stored Fernet-encrypted)
* otherwise                     -> MFA_REQUIRED
``POST /admin/auth/mfa/verify`` checks the TOTP, completes enrollment / the forced password change, and issues
an admin access token + rotating refresh token (``admin_sessions``, hashed, reuse revokes the family).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import ratelimit
from app.core.context import AdminPrincipal
from app.core.db import independent_session
from app.core.errors import (
    AccountSuspendedError,
    InvalidCredentialsError,
    MfaInvalidError,
    UnauthenticatedError,
    ValidationFailedError,
)
from app.core.security import (
    accept_totp,
    burn_password_check,
    check_password_policy,
    create_admin_access_token,
    create_mfa_token,
    decode_mfa_token,
    decrypt_secret,
    encrypt_secret,
    hash_password,
    hash_token,
    new_refresh_token,
    new_totp_secret,
    totp_uri,
    verify_password,
)
from app.modules.identity.interface import TokenOut
from app.modules.superadmin import repository as repo
from app.modules.superadmin.interface import write_platform_audit
from app.modules.superadmin.models import AdminSession, PlatformAdmin
from app.modules.superadmin.schemas import AdminLoginIn, AdminLoginOut, AdminLoginSuccessOut, AdminMeOut

#: Admin refresh sessions are short-lived (the console also logs out after 30 min idle).
ADMIN_REFRESH_TTL = timedelta(hours=12)
TOTP_ISSUER = "InaiFlow Admin"


def _rl_key(email: str) -> str:
    """Separate rate-limit namespace from tenant users sharing the same email."""
    return f"admin:{email}"


@dataclass(frozen=True, slots=True)
class AdminIssued:
    body: AdminLoginSuccessOut
    refresh_token: str


def _now() -> datetime:
    return datetime.now(UTC)


def me_out(a: PlatformAdmin) -> AdminMeOut:
    return AdminMeOut(id=a.id, email=a.email, full_name=a.full_name, role=a.role, mfa_enabled=a.mfa_enabled,
                      last_login_at=a.last_login_at)  # fmt: skip


async def login(db: AsyncSession, body: AdminLoginIn, ip: str | None) -> AdminLoginOut:
    email = body.email.strip().lower()
    await ratelimit.check_login_allowed(db, _rl_key(email), ip)
    admin = await repo.admin_by_email(db, email)
    if admin is None:
        await burn_password_check(body.password)
        await ratelimit.record_login_attempt(_rl_key(email), ip, False)
        raise InvalidCredentialsError()
    if not await verify_password(admin.password_hash, body.password):
        await ratelimit.record_login_attempt(_rl_key(email), ip, False)
        raise InvalidCredentialsError()
    if not admin.is_active:
        raise AccountSuspendedError("This admin account is deactivated")
    await ratelimit.record_login_attempt(_rl_key(email), ip, True)
    uri = None
    if not admin.mfa_enabled:
        if not admin.mfa_secret:  # keep a pending secret stable across retries until enrollment completes
            admin.mfa_secret = encrypt_secret(new_totp_secret())
            await db.flush()
        uri = totp_uri(decrypt_secret(admin.mfa_secret), admin.email, TOTP_ISSUER)
    if admin.must_change_password:
        status = "PASSWORD_CHANGE_REQUIRED"
    elif not admin.mfa_enabled:
        status = "MFA_SETUP_REQUIRED"
    else:
        status = "MFA_REQUIRED"
    token = create_mfa_token(user_id=admin.id, remember=False, admin=True)
    return AdminLoginOut(status=status, mfa_token=token, otpauth_uri=uri)


async def _start_session(db: AsyncSession, admin: PlatformAdmin, ip: str | None, ua: str | None,
                         family_id: uuid.UUID | None = None) -> AdminIssued:  # fmt: skip
    raw = new_refresh_token()
    session = AdminSession(admin_id=admin.id, family_id=family_id or uuid.uuid4(), token_hash=hash_token(raw),
                           user_agent=ua, ip=ip, expires_at=_now() + ADMIN_REFRESH_TTL)  # fmt: skip
    await repo.add(db, session)
    token, expires_in = create_admin_access_token(admin_id=admin.id, session_id=session.family_id, email=admin.email,
                                                  role=admin.role)  # fmt: skip
    out = AdminLoginSuccessOut(token=TokenOut(access_token=token, token_type="bearer", expires_in=expires_in),  # noqa: S106
                               admin=me_out(admin))  # fmt: skip
    return AdminIssued(out, raw)


async def verify_mfa(db: AsyncSession, mfa_token: str, code: str, new_password: str | None, ip: str | None,
                     ua: str | None) -> AdminIssued:  # fmt: skip
    payload = decode_mfa_token(mfa_token, admin=True)
    try:
        admin_id = uuid.UUID(str(payload["sub"]))
    except (KeyError, ValueError) as exc:
        raise UnauthenticatedError("Invalid token") from exc
    admin = await repo.admin_by_id(db, admin_id, lock=True)
    if admin is None or not admin.mfa_secret:
        raise UnauthenticatedError("Invalid token")
    if not admin.is_active:
        raise AccountSuspendedError("This admin account is deactivated")
    await ratelimit.check_login_allowed(db, _rl_key(admin.email), ip)
    if not accept_totp(admin, code):
        await ratelimit.record_login_attempt(_rl_key(admin.email), ip, False)
        raise MfaInvalidError()
    changes: dict[str, object] = {}
    if admin.must_change_password:
        if not new_password:
            raise ValidationFailedError("A new password is required", {"new_password": ["required"]})
        check_password_policy(new_password, admin.email)
        if await verify_password(admin.password_hash, new_password):
            raise ValidationFailedError("Choose a password different from the temporary one")
        admin.password_hash = await hash_password(new_password)
        admin.must_change_password = False
        await repo.revoke_admin_sessions(db, admin.id, "PASSWORD_CHANGED")
        changes["password_changed"] = True
    if not admin.mfa_enabled:
        admin.mfa_enabled = True
        changes["mfa_enrolled"] = True
    admin.last_login_at = _now()
    issued = await _start_session(db, admin, ip, ua)
    principal = AdminPrincipal(admin.id, uuid.uuid4(), admin.email, admin.role, ip, ua)
    await write_platform_audit(db, principal, "ADMIN_LOGIN", "PLATFORM_ADMIN", admin.id, after=changes or None)
    return issued


async def _revoke_family_now(family_id: uuid.UUID, reason: str) -> None:
    async with independent_session() as s:
        await repo.revoke_family(s, family_id, reason)


async def refresh(db: AsyncSession, raw: str | None, ip: str | None, ua: str | None) -> AdminIssued:
    if not raw:
        raise UnauthenticatedError("No refresh token")
    session = await repo.session_by_hash(db, hash_token(raw))
    if session is None:
        raise UnauthenticatedError("Invalid refresh token")
    if session.revoked_at is not None:
        if session.revoke_reason == "ROTATED":  # replay of a rotated token: assume theft
            await _revoke_family_now(session.family_id, "REUSE_DETECTED")
        raise UnauthenticatedError("Invalid refresh token")
    if session.expires_at <= _now():
        raise UnauthenticatedError("Refresh token expired")
    admin = await repo.admin_by_id(db, session.admin_id)
    if admin is None or not admin.is_active:
        await _revoke_family_now(session.family_id, "DEACTIVATED")
        raise AccountSuspendedError("This admin account is deactivated")
    if not admin.mfa_enabled:
        raise UnauthenticatedError("Invalid refresh token")
    if not await repo.claim_rotation(db, session.id):
        await _revoke_family_now(session.family_id, "REUSE_DETECTED")
        raise UnauthenticatedError("Invalid refresh token")
    issued = await _start_session(db, admin, ip, ua, family_id=session.family_id)
    new = await repo.session_by_hash(db, hash_token(issued.refresh_token))
    if new is not None:
        await repo.set_replaced_by(db, session.id, new.id)
    return issued


async def logout(db: AsyncSession, raw: str | None) -> None:
    if not raw:
        return
    session = await repo.session_by_hash(db, hash_token(raw))
    if session is not None:
        await repo.revoke_family(db, session.family_id, "LOGOUT")


async def get_me(db: AsyncSession, admin: AdminPrincipal) -> AdminMeOut:
    a = await repo.admin_by_id(db, admin.admin_id)
    if a is None:
        raise UnauthenticatedError()
    return me_out(a)
