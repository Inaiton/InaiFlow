"""Passwords (argon2id), JWT (user + admin audiences), refresh tokens, one-time codes, TOTP, Fernet."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import secrets
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

import jwt
import pyotp
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings
from app.core.errors import (
    TokenExpiredError,
    UnauthenticatedError,
    ValidationFailedError,
)

ISSUER = "inaiflow"
USER_AUDIENCE = "inaiflow-user"
ADMIN_AUDIENCE = "inaiflow-admin"
TOTP_ISSUER = "InaiFlow"

_PASSWORDS_FILE = Path(__file__).parent / "data" / "common_passwords.txt"


def utcnow() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------- passwords
@lru_cache
def _hasher() -> PasswordHasher:
    s = get_settings()
    return PasswordHasher(
        time_cost=s.ARGON2_TIME_COST, memory_cost=s.ARGON2_MEMORY_KIB, parallelism=s.ARGON2_PARALLELISM
    )


def hash_password_sync(password: str) -> str:
    return _hasher().hash(password)


def verify_password_sync(password_hash: str | None, password: str) -> bool:
    if not password_hash:
        return False
    try:
        return _hasher().verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


async def hash_password(password: str) -> str:
    return await asyncio.to_thread(hash_password_sync, password)


async def verify_password(password_hash: str | None, password: str) -> bool:
    return await asyncio.to_thread(verify_password_sync, password_hash, password)


_DUMMY_HASH: str | None = None


async def burn_password_check(password: str) -> None:
    """Spend the same time as a real verification (no user enumeration through timing)."""
    global _DUMMY_HASH
    if _DUMMY_HASH is None:
        _DUMMY_HASH = await hash_password("dummy-password-for-timing")
    await verify_password(_DUMMY_HASH, password)


@lru_cache
def _common_passwords() -> frozenset[str]:
    try:
        return frozenset(_PASSWORDS_FILE.read_text().split())
    except OSError:  # pragma: no cover
        return frozenset()


def check_password_policy(password: str, email: str | None = None) -> None:
    """10–128 chars, not equal to the email (or its local part), not in the bundled top-10k list."""
    problems: list[str] = []
    if len(password) < 10:
        problems.append("Password must be at least 10 characters")
    if len(password) > 128:
        problems.append("Password must be at most 128 characters")
    lowered = password.lower()
    if email:
        e = email.lower()
        if lowered in (e, e.split("@")[0]):
            problems.append("Password must not be your email address")
    if lowered in _common_passwords():
        problems.append("This password is too common")
    if problems:
        raise ValidationFailedError(problems[0], {"password": problems})


# ---------------------------------------------------------------- opaque tokens & codes
def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def new_refresh_token() -> str:
    """256-bit random refresh token (url-safe)."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return sha256_hex(token)


def new_numeric_code(digits: int = 6) -> str:
    return f"{secrets.randbelow(10**digits):0{digits}d}"


def hash_code(purpose: str, email: str, code: str) -> str:
    """Keyed hash for one-time codes (bound to purpose+email so codes are not reusable elsewhere)."""
    key = get_settings().JWT_SECRET.encode()
    msg = f"{purpose}:{email.lower()}:{code}".encode()
    return hmac.new(key, msg, hashlib.sha256).hexdigest()


def constant_time_equals(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


def new_recovery_codes(count: int = 10) -> list[str]:
    alphabet = "abcdefghjkmnpqrstuvwxyz23456789"
    codes = []
    for _ in range(count):
        raw = "".join(secrets.choice(alphabet) for _ in range(8))
        codes.append(f"{raw[:4]}-{raw[4:]}")
    return codes


def normalize_recovery_code(code: str) -> str:
    c = code.strip().lower().replace(" ", "")
    if "-" not in c and len(c) == 8:
        c = f"{c[:4]}-{c[4:]}"
    return c


# ---------------------------------------------------------------- JWT
@dataclass(frozen=True, slots=True)
class AccessClaims:
    sub: uuid.UUID
    sid: uuid.UUID
    email: str
    mfa: bool
    imp: dict[str, Any] | None
    exp: datetime


def _encode(payload: dict[str, Any], secret: str) -> str:
    return jwt.encode(payload, secret, algorithm="HS256")


def _decode(token: str, secret: str, audience: str, typ: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            audience=audience,
            issuer=ISSUER,
            options={"require": ["exp", "iat", "sub", "typ", "aud", "iss"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenExpiredError() from exc
    except jwt.PyJWTError as exc:
        raise UnauthenticatedError("Invalid token") from exc
    if payload.get("typ") != typ:
        raise UnauthenticatedError("Invalid token type")
    return payload


def create_access_token(
    *,
    user_id: uuid.UUID,
    session_id: uuid.UUID,
    email: str,
    mfa: bool,
    imp: dict[str, Any] | None = None,
    ttl_seconds: int | None = None,
) -> tuple[str, int]:
    """Return ``(jwt, expires_in_seconds)`` for the user audience."""
    s = get_settings()
    ttl = ttl_seconds or s.ACCESS_TOKEN_TTL_SECONDS
    now = utcnow()
    payload: dict[str, Any] = {
        "iss": ISSUER,
        "aud": USER_AUDIENCE,
        "typ": "access",
        "sub": str(user_id),
        "sid": str(session_id),
        "email": email,
        "mfa": bool(mfa),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=ttl)).timestamp()),
        "jti": secrets.token_hex(8),
    }
    if imp is not None:
        payload["imp"] = imp
    return _encode(payload, s.JWT_SECRET), ttl


def decode_access_token(token: str) -> AccessClaims:
    p = _decode(token, get_settings().JWT_SECRET, USER_AUDIENCE, "access")
    try:
        return AccessClaims(
            sub=uuid.UUID(p["sub"]),
            sid=uuid.UUID(p["sid"]),
            email=str(p.get("email", "")),
            mfa=bool(p.get("mfa", False)),
            imp=p.get("imp"),
            exp=datetime.fromtimestamp(p["exp"], UTC),
        )
    except (KeyError, ValueError, TypeError) as exc:
        raise UnauthenticatedError("Invalid token") from exc


def create_impersonation_token(
    *, admin_id: uuid.UUID, session_id: uuid.UUID, org_id: uuid.UUID, mode: str, expires_at: datetime
) -> str:
    """User-audience access token carrying ``imp``; ``sub`` = admin id, ``sid`` = impersonation session id.

    Used by the superadmin module (S5) for ``POST /admin/organizations/{id}/impersonate``.
    """
    ttl = max(1, int((expires_at - utcnow()).total_seconds()))
    imp = {"session_id": str(session_id), "admin_id": str(admin_id), "org_id": str(org_id), "mode": mode}
    token, _ = create_access_token(
        user_id=admin_id, session_id=session_id, email="", mfa=True, imp=imp, ttl_seconds=ttl
    )
    return token


def create_mfa_token(*, user_id: uuid.UUID, remember: bool, admin: bool = False) -> str:
    s = get_settings()
    now = utcnow()
    payload = {
        "iss": ISSUER,
        "aud": ADMIN_AUDIENCE if admin else USER_AUDIENCE,
        "typ": "mfa",
        "sub": str(user_id),
        "remember": bool(remember),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=s.MFA_TOKEN_TTL_SECONDS)).timestamp()),
        "jti": secrets.token_hex(8),
    }
    return _encode(payload, s.ADMIN_JWT_SECRET if admin else s.JWT_SECRET)


def decode_mfa_token(token: str, *, admin: bool = False) -> dict[str, Any]:
    s = get_settings()
    if admin:
        return _decode(token, s.ADMIN_JWT_SECRET, ADMIN_AUDIENCE, "mfa")
    return _decode(token, s.JWT_SECRET, USER_AUDIENCE, "mfa")


def create_admin_access_token(*, admin_id: uuid.UUID, session_id: uuid.UUID, email: str, role: str) -> tuple[str, int]:
    s = get_settings()
    ttl = s.ACCESS_TOKEN_TTL_SECONDS
    now = utcnow()
    payload = {
        "iss": ISSUER,
        "aud": ADMIN_AUDIENCE,
        "typ": "access",
        "sub": str(admin_id),
        "sid": str(session_id),
        "email": email,
        "role": role,
        "mfa": True,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=ttl)).timestamp()),
        "jti": secrets.token_hex(8),
    }
    return _encode(payload, s.ADMIN_JWT_SECRET), ttl


def decode_admin_access_token(token: str) -> dict[str, Any]:
    return _decode(token, get_settings().ADMIN_JWT_SECRET, ADMIN_AUDIENCE, "access")


def encode_signed_payload(payload: dict[str, Any], *, ttl_seconds: int, purpose: str) -> str:
    """Short-lived signed blob (OAuth state, local storage tokens)."""
    s = get_settings()
    now = utcnow()
    body = {
        **payload,
        "iss": ISSUER,
        "aud": f"inaiflow-{purpose}",
        "typ": purpose,
        "sub": purpose,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=ttl_seconds)).timestamp()),
    }
    return _encode(body, s.JWT_SECRET)


def decode_signed_payload(token: str, *, purpose: str) -> dict[str, Any]:
    return _decode(token, get_settings().JWT_SECRET, f"inaiflow-{purpose}", purpose)


# ---------------------------------------------------------------- TOTP + Fernet
def new_totp_secret() -> str:
    return pyotp.random_base32()


def totp_uri(secret: str, account: str, issuer: str = TOTP_ISSUER) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=account, issuer_name=issuer)


def verify_totp(secret: str, code: str) -> bool:
    code = (code or "").strip().replace(" ", "")
    if not code.isdigit() or len(code) != 6:
        return False
    return pyotp.TOTP(secret).verify(code, valid_window=1)


def accept_totp(holder: Any, code: str) -> bool:
    """Verify a TOTP code for a user/admin row and burn its time step, so a code can't be replayed."""
    code = (code or "").strip().replace(" ", "")
    if not holder.mfa_secret or not code.isdigit() or len(code) != 6:
        return False
    totp, now = pyotp.TOTP(decrypt_secret(holder.mfa_secret)), int(time.time()) // 30
    for step in (now - 1, now, now + 1):
        if step > (holder.mfa_last_step or 0) and hmac.compare_digest(totp.at(step * 30), code):
            holder.mfa_last_step = step
            return True
    return False


def current_totp(secret: str) -> str:
    """Testing/CLI helper."""
    return pyotp.TOTP(secret).now()


@lru_cache
def _fernet() -> Fernet:
    return Fernet(get_settings().MFA_ENCRYPTION_KEY.encode())


def encrypt_secret(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt_secret(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken as exc:
        raise UnauthenticatedError("Unable to read MFA secret") from exc


def csv_safe(value: object) -> object:
    """Neutralise spreadsheet formula injection in exported text cells; numbers (incl. "-12.50") pass through."""
    if not isinstance(value, str) or value[:1] not in ("=", "+", "-", "@", "\t", "\r"):
        return value
    try:
        float(value)
        return value
    except ValueError:
        return "'" + value
