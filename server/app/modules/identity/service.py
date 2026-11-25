"""Identity services: signup/verify/login/MFA/refresh rotation/reset, Google OAuth, personal profile."""

from __future__ import annotations

import base64
import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.email import EmailMessage, get_email
from app.adapters.storage import IMAGE_MIME_ALLOWLIST, build_user_key, get_storage, validate_upload
from app.core import ratelimit
from app.core.config import get_settings
from app.core.db import independent_session
from app.core.errors import (
    AccountSuspendedError,
    ConflictError,
    EmailNotVerifiedError,
    InvalidCredentialsError,
    MfaInvalidError,
    NotFoundError,
    UnauthenticatedError,
    ValidationFailedError,
)
from app.core.schemas import UploadTicket
from app.core.security import (
    accept_totp,
    burn_password_check,
    check_password_policy,
    create_access_token,
    create_mfa_token,
    decode_mfa_token,
    decode_signed_payload,
    encode_signed_payload,
    encrypt_secret,
    hash_code,
    hash_password,
    hash_token,
    new_numeric_code,
    new_recovery_codes,
    new_refresh_token,
    new_totp_secret,
    normalize_recovery_code,
    totp_uri,
    verify_password,
)
from app.modules.identity import repository as repo
from app.modules.identity.models import AuthOneTimeCode, User, UserMfaRecoveryCode, UserSession
from app.modules.identity.schemas import (
    LoginIn,
    LoginOut,
    LoginSuccessOut,
    MeFileUploadIn,
    MeOut,
    MeUpdateIn,
    MfaSetupOut,
    PasswordChangeIn,
    PasswordResetIn,
    RecoveryCodesOut,
    SessionOut,
    SignupIn,
    SignupOut,
    TokenOut,
)

CODE_TTL = timedelta(minutes=10)
MAX_CODE_ATTEMPTS = 5
EMAIL_VERIFY, PASSWORD_RESET = "EMAIL_VERIFY", "PASSWORD_RESET"
INVALID_CODE = "The code is invalid or has expired"


@dataclass(frozen=True, slots=True)
class Issued:
    """Result of a successful authentication: the router sets the refresh cookie."""

    body: LoginSuccessOut
    refresh_token: str
    remember: bool


def _now() -> datetime:
    return datetime.now(UTC)


def _norm(email: str) -> str:
    return email.strip().lower()


# ---------------------------------------------------------------- presentation
async def me_out(user: User) -> MeOut:
    storage = get_storage()
    avatar = user.avatar_url
    signature = user.digital_signature_url
    if user.avatar_storage_key:
        avatar = (await storage.create_download_url(user.avatar_storage_key)).url
    if user.signature_storage_key:
        signature = (await storage.create_download_url(user.signature_storage_key)).url
    return MeOut(id=user.id, email=user.email, full_name=user.full_name, mobile=user.mobile,
                 professional_reg_no=user.professional_reg_no, avatar_url=avatar, signature_url=signature,
                 is_email_verified=user.is_email_verified, mfa_enabled=user.mfa_enabled,
                 created_at=user.created_at)  # fmt: skip


# ---------------------------------------------------------------- one-time codes
async def _issue_code(db: AsyncSession, user: User, purpose: str) -> None:
    if not await ratelimit.check_code_send_allowed(db, user.email, purpose):
        return  # silently drop (no enumeration, no spam)
    await repo.invalidate_codes(db, user.email, purpose)
    code = new_numeric_code()
    await repo.add(db, AuthOneTimeCode(subject_type="USER", subject_id=user.id, email=user.email, purpose=purpose,
                                       code_hash=hash_code(purpose, user.email, code), expires_at=_now() + CODE_TTL))  # fmt: skip
    if purpose == EMAIL_VERIFY:
        subject, text = "Verify your InaiFlow email", f"Your verification code is {code}. It expires in 10 minutes."
    else:
        subject, text = "Reset your InaiFlow password", f"Your password reset code is {code}. It expires in 10 minutes."
    await get_email().send(EmailMessage(user.email, subject, text, tag=purpose))


async def _consume_code(db: AsyncSession, email: str, purpose: str, code: str) -> None:
    row = await repo.latest_code(db, email, purpose)
    if row is None or row.attempts >= MAX_CODE_ATTEMPTS:
        raise ValidationFailedError(INVALID_CODE)
    if hash_code(purpose, email, code.strip()) != row.code_hash:
        async with independent_session() as s:  # survive the failing request
            from sqlalchemy import update

            await s.execute(update(AuthOneTimeCode).where(AuthOneTimeCode.id == row.id)
                            .values(attempts=AuthOneTimeCode.attempts + 1))  # fmt: skip
        raise ValidationFailedError(INVALID_CODE)
    if not await repo.claim_code(db, row.id):
        raise ValidationFailedError(INVALID_CODE)


# ---------------------------------------------------------------- sessions & tokens
async def _start_session(
    db: AsyncSession, user: User, *, remember: bool, mfa: bool, ip: str | None, ua: str | None,
    family_id: uuid.UUID | None = None,
) -> Issued:  # fmt: skip
    s = get_settings()
    raw = new_refresh_token()
    ttl = timedelta(days=s.REFRESH_TTL_REMEMBER_DAYS if remember else s.REFRESH_TTL_DAYS)
    session = UserSession(user_id=user.id, family_id=family_id or uuid.uuid4(), token_hash=hash_token(raw),
                          user_agent=ua, ip=ip, remember=remember, expires_at=_now() + ttl)  # fmt: skip
    await repo.add(db, session)
    token, expires_in = create_access_token(user_id=user.id, session_id=session.family_id, email=user.email, mfa=mfa)
    user.last_login_at = _now()
    token_out = TokenOut(access_token=token, token_type="bearer", expires_in=expires_in)  # noqa: S106
    body = LoginSuccessOut(token=token_out, user=await me_out(user))
    return Issued(body, raw, remember)


# ---------------------------------------------------------------- signup / verify
async def signup(db: AsyncSession, body: SignupIn) -> SignupOut:
    email = _norm(body.email)
    check_password_policy(body.password, email)
    existing = await repo.user_by_email(db, email)
    if existing is not None:
        if existing.is_email_verified:
            await get_email().send(EmailMessage(email, "InaiFlow sign-up attempt",
                                                "Someone tried to create an InaiFlow account with your email. "
                                                "If it was you, sign in or reset your password instead.",
                                                tag="SIGNUP_EXISTING"))  # fmt: skip
        else:
            await _issue_code(db, existing, EMAIL_VERIFY)
        return SignupOut(email=email, verification_required=True)
    user = User(email=email, full_name=body.full_name.strip(), password_hash=await hash_password(body.password),
                oauth_provider="LOCAL")  # fmt: skip
    await repo.add(db, user)
    await _issue_code(db, user, EMAIL_VERIFY)
    return SignupOut(email=email, verification_required=True)


async def verify_email(db: AsyncSession, email: str, code: str) -> None:
    email = _norm(email)
    await _consume_code(db, email, EMAIL_VERIFY, code)
    user = await repo.user_by_email(db, email)
    if user is None:
        raise ValidationFailedError(INVALID_CODE)
    user.is_email_verified = True
    user.updated_at = _now()


async def resend_verification(db: AsyncSession, email: str) -> None:
    user = await repo.user_by_email(db, _norm(email))
    if user is not None and not user.is_email_verified:
        await _issue_code(db, user, EMAIL_VERIFY)


# ---------------------------------------------------------------- login / MFA
async def login(db: AsyncSession, body: LoginIn, ip: str | None, ua: str | None) -> tuple[LoginOut, Issued | None]:
    email = _norm(body.email)
    await ratelimit.check_login_allowed(db, email, ip)
    user = await repo.user_by_email(db, email)
    if user is None or not user.password_hash:
        await burn_password_check(body.password)
        await ratelimit.record_login_attempt(email, ip, False)
        raise InvalidCredentialsError()
    if not await verify_password(user.password_hash, body.password):
        await ratelimit.record_login_attempt(email, ip, False)
        raise InvalidCredentialsError()
    if user.is_suspended:
        raise AccountSuspendedError()
    if not user.is_email_verified:
        raise EmailNotVerifiedError()
    await ratelimit.record_login_attempt(email, ip, True)
    if user.mfa_enabled:
        token = create_mfa_token(user_id=user.id, remember=body.remember)
        return LoginOut(status="MFA_REQUIRED", token=None, mfa_token=token, user=None), None
    issued = await _start_session(db, user, remember=body.remember, mfa=False, ip=ip, ua=ua)
    return LoginOut(status="OK", token=issued.body.token, mfa_token=None, user=issued.body.user), issued


async def _check_second_factor(db: AsyncSession, user: User, code: str) -> bool:
    """TOTP code or an unused recovery code (consumed on success)."""
    if accept_totp(user, code):
        return True
    normalized = normalize_recovery_code(code)
    for rc in await repo.recovery_codes(db, user.id):
        if await verify_password(rc.code_hash, normalized):
            rc.used_at = _now()
            return True
    return False


async def verify_mfa(db: AsyncSession, mfa_token: str, code: str, ip: str | None, ua: str | None) -> Issued:
    payload = decode_mfa_token(mfa_token)
    user = await repo.user_by_id(db, uuid.UUID(payload["sub"]))
    if user is None or not user.mfa_enabled:
        raise UnauthenticatedError("Invalid token")
    await ratelimit.check_login_allowed(db, user.email, ip)
    if user.is_suspended:
        raise AccountSuspendedError()
    if not await _check_second_factor(db, user, code):
        await ratelimit.record_login_attempt(user.email, ip, False)
        raise MfaInvalidError()
    return await _start_session(db, user, remember=bool(payload.get("remember")), mfa=True, ip=ip, ua=ua)


# ---------------------------------------------------------------- refresh / logout
async def _revoke_family_now(family_id: uuid.UUID, reason: str) -> None:
    async with independent_session() as s:
        await repo.revoke_family(s, family_id, reason)


async def refresh(db: AsyncSession, raw: str | None, ip: str | None, ua: str | None) -> Issued:
    if not raw:
        raise UnauthenticatedError("No refresh token")
    session = await repo.session_by_hash(db, hash_token(raw))
    if session is None:
        raise UnauthenticatedError("Invalid refresh token")
    if session.revoked_at is not None:
        if session.revoke_reason == "ROTATED":
            # A rotated token was replayed: assume theft and kill the whole family.
            await _revoke_family_now(session.family_id, "REUSE_DETECTED")
        raise UnauthenticatedError("Invalid refresh token")
    if session.expires_at <= _now():
        raise UnauthenticatedError("Refresh token expired")
    user = await repo.user_by_id(db, session.user_id)
    if user is None or user.is_suspended:
        await _revoke_family_now(session.family_id, "SUSPENDED")
        raise UnauthenticatedError("Invalid refresh token")
    if not await repo.claim_rotation(db, session.id):
        await _revoke_family_now(session.family_id, "REUSE_DETECTED")
        raise UnauthenticatedError("Invalid refresh token")
    # MFA-enabled users can only hold sessions created through MFA (enable revokes other sessions).
    issued = await _start_session(db, user, remember=session.remember, mfa=user.mfa_enabled, ip=ip, ua=ua,
                                  family_id=session.family_id)  # fmt: skip
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


# ---------------------------------------------------------------- password reset
async def forgot_password(db: AsyncSession, email: str) -> None:
    user = await repo.user_by_email(db, _norm(email))
    if user is not None and not user.is_suspended:
        await _issue_code(db, user, PASSWORD_RESET)


async def reset_password(db: AsyncSession, body: PasswordResetIn) -> None:
    email = _norm(body.email)
    check_password_policy(body.new_password, email)
    await _consume_code(db, email, PASSWORD_RESET, body.code)
    user = await repo.user_by_email(db, email)
    if user is None:
        raise ValidationFailedError(INVALID_CODE)
    user.password_hash = await hash_password(body.new_password)
    user.is_email_verified = True
    user.updated_at = _now()
    await repo.revoke_user_sessions(db, user.id, "PASSWORD_RESET")


# ---------------------------------------------------------------- Google OAuth (OIDC code + PKCE)
GOOGLE_AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN = "https://oauth2.googleapis.com/token"  # noqa: S105
GOOGLE_JWKS = "https://www.googleapis.com/oauth2/v3/certs"


def _require_google() -> None:
    if not get_settings().google_enabled:
        raise NotFoundError()


def _safe_redirect(path: str | None) -> str:
    if not path or not path.startswith("/") or path.startswith("//") or "\\" in path:
        return "/"
    return path


def google_start(redirect_to: str | None) -> tuple[str, str]:
    """Return (authorization URL, signed state cookie value)."""
    _require_google()
    s = get_settings()
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    nonce = secrets.token_urlsafe(16)
    state = secrets.token_urlsafe(16)
    cookie = encode_signed_payload({"state": state, "verifier": verifier, "nonce": nonce,
                                    "redirect_to": _safe_redirect(redirect_to)}, ttl_seconds=600, purpose="oauth")  # fmt: skip
    params = {"client_id": s.GOOGLE_CLIENT_ID, "redirect_uri": google_redirect_uri(), "response_type": "code",
              "scope": "openid email profile", "state": state, "nonce": nonce, "code_challenge": challenge,
              "code_challenge_method": "S256", "prompt": "select_account"}  # fmt: skip
    return f"{GOOGLE_AUTH}?{urlencode(params)}", cookie


def google_redirect_uri() -> str:
    s = get_settings()
    return s.GOOGLE_REDIRECT_URI or f"{s.PUBLIC_USER_WEB_URL.rstrip('/')}/api/v1/auth/oauth/google/callback"


async def google_callback(
    db: AsyncSession, code: str, state: str, cookie: str | None, ip: str | None, ua: str | None
) -> tuple[Issued, str]:
    _require_google()
    if not cookie:
        raise UnauthenticatedError("OAuth state missing")
    saved = decode_signed_payload(cookie, purpose="oauth")
    if not secrets.compare_digest(str(saved.get("state")), state):
        raise UnauthenticatedError("OAuth state mismatch")
    s = get_settings()
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(GOOGLE_TOKEN, data={
            "code": code, "client_id": s.GOOGLE_CLIENT_ID, "client_secret": s.GOOGLE_CLIENT_SECRET,
            "redirect_uri": google_redirect_uri(), "grant_type": "authorization_code",
            "code_verifier": saved["verifier"]})  # fmt: skip
    if resp.status_code >= 400:
        raise UnauthenticatedError("Google sign-in failed")
    import jwt

    id_token = resp.json().get("id_token", "")
    signing_key = jwt.PyJWKClient(GOOGLE_JWKS).get_signing_key_from_jwt(id_token)
    claims = jwt.decode(id_token, signing_key.key, algorithms=["RS256"], audience=s.GOOGLE_CLIENT_ID,
                        issuer=["https://accounts.google.com", "accounts.google.com"])  # fmt: skip
    if claims.get("nonce") != saved.get("nonce") or not claims.get("email_verified"):
        raise UnauthenticatedError("Google account email is not verified")
    user = await _user_for_google(db, claims)
    if user.is_suspended:
        raise AccountSuspendedError()
    if user.mfa_enabled:
        # MFA users finish in the web app with the mfa_token flow; refuse silent token issue here.
        raise UnauthenticatedError("Two-factor users must sign in with email and password")
    issued = await _start_session(db, user, remember=False, mfa=False, ip=ip, ua=ua)
    return issued, saved.get("redirect_to") or "/"


async def _user_for_google(db: AsyncSession, claims: dict) -> User:
    user = await repo.user_by_oauth(db, "GOOGLE", str(claims["sub"]))
    if user:
        return user
    email = _norm(claims["email"])
    user = await repo.user_by_email(db, email)
    if user is None:
        user = User(email=email, full_name=claims.get("name") or email.split("@")[0], oauth_provider="GOOGLE",
                    oauth_subject_id=str(claims["sub"]), is_email_verified=True)  # fmt: skip
        await repo.add(db, user)
    else:
        user.oauth_subject_id = user.oauth_subject_id or str(claims["sub"])
        user.is_email_verified = True
    return user


# ---------------------------------------------------------------- personal profile (/me)
async def _me(db: AsyncSession, user_id: uuid.UUID) -> User:
    user = await repo.user_by_id(db, user_id)
    if user is None:
        raise UnauthenticatedError()
    return user


async def get_me(db: AsyncSession, user_id: uuid.UUID) -> MeOut:
    return await me_out(await _me(db, user_id))


async def _check_own_key(user_id: uuid.UUID, key: str, purpose: str) -> None:
    if not key.startswith(f"users/{user_id}/{purpose}/"):
        raise ValidationFailedError("This file does not belong to you")
    if await get_storage().head(key) is None:
        raise ValidationFailedError("The file was not uploaded")


async def update_me(db: AsyncSession, user_id: uuid.UUID, body: MeUpdateIn) -> MeOut:
    user = await _me(db, user_id)
    data = body.model_dump(exclude_unset=True)
    if "full_name" in data and data["full_name"]:
        user.full_name = data["full_name"]
    for field in ("mobile", "professional_reg_no"):
        if field in data:
            setattr(user, field, data[field])
    for field, purpose in (("avatar_storage_key", "avatar"), ("signature_storage_key", "signature")):
        if field in data:
            if data[field]:
                await _check_own_key(user.id, data[field], purpose)
            setattr(user, field, data[field])
    user.updated_at = _now()
    return await me_out(user)


async def me_upload_url(user_id: uuid.UUID, body: MeFileUploadIn) -> UploadTicket:
    validate_upload(body.content_type, body.size_bytes, IMAGE_MIME_ALLOWLIST, 5 * 1024 * 1024)
    ext = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}[body.content_type.split(";")[0].lower()]
    key = build_user_key(user_id, body.purpose, f"{body.purpose.lower()}.{ext}")
    t = await get_storage().create_upload_ticket(key, body.content_type, body.size_bytes)
    return UploadTicket(upload_url=t.upload_url, method=t.method, headers=t.headers, storage_key=t.storage_key,
                        expires_at=t.expires_at)  # fmt: skip


async def change_password(db: AsyncSession, user_id: uuid.UUID, family_id: uuid.UUID, body: PasswordChangeIn) -> None:
    user = await _me(db, user_id)
    if not await verify_password(user.password_hash, body.current_password):
        raise InvalidCredentialsError("The current password is incorrect")
    check_password_policy(body.new_password, user.email)
    user.password_hash = await hash_password(body.new_password)
    user.updated_at = _now()
    await repo.revoke_user_sessions(db, user.id, "PASSWORD_CHANGED", except_family=family_id)


async def mfa_setup(db: AsyncSession, user_id: uuid.UUID) -> MfaSetupOut:
    user = await _me(db, user_id)
    if user.mfa_enabled:
        raise ConflictError("Two-factor authentication is already enabled")
    secret = new_totp_secret()
    user.mfa_secret = encrypt_secret(secret)
    return MfaSetupOut(secret=secret, otpauth_uri=totp_uri(secret, user.email))


async def _new_recovery_codes(db: AsyncSession, user: User) -> list[str]:
    await repo.delete_recovery_codes(db, user.id)
    codes = new_recovery_codes()
    for c in codes:
        db.add(UserMfaRecoveryCode(user_id=user.id, code_hash=await hash_password(c)))
    await db.flush()
    return codes


async def mfa_enable(db: AsyncSession, user_id: uuid.UUID, family_id: uuid.UUID, code: str) -> RecoveryCodesOut:
    user = await _me(db, user_id)
    if user.mfa_enabled:
        raise ConflictError("Two-factor authentication is already enabled")
    if not accept_totp(user, code):
        raise MfaInvalidError()
    user.mfa_enabled = True
    user.updated_at = _now()
    await repo.revoke_user_sessions(db, user.id, "MFA_ENABLED", except_family=family_id)
    return RecoveryCodesOut(recovery_codes=await _new_recovery_codes(db, user))


async def mfa_disable(db: AsyncSession, user_id: uuid.UUID, password: str, code: str) -> None:
    user = await _me(db, user_id)
    if not user.mfa_enabled:
        raise ConflictError("Two-factor authentication is not enabled")
    if not await verify_password(user.password_hash, password):
        raise InvalidCredentialsError("The password is incorrect")
    if not await _check_second_factor(db, user, code):
        raise MfaInvalidError()
    user.mfa_enabled, user.mfa_secret = False, None
    user.updated_at = _now()
    await repo.delete_recovery_codes(db, user.id)


async def mfa_regenerate_codes(db: AsyncSession, user_id: uuid.UUID, code: str) -> RecoveryCodesOut:
    user = await _me(db, user_id)
    if not user.mfa_enabled or not accept_totp(user, code):
        raise MfaInvalidError()
    return RecoveryCodesOut(recovery_codes=await _new_recovery_codes(db, user))


async def list_sessions(db: AsyncSession, user_id: uuid.UUID, current_family: uuid.UUID) -> list[SessionOut]:
    out = []
    for s, started in await repo.active_sessions(db, user_id):
        out.append(SessionOut(id=s.family_id, user_agent=s.user_agent, ip=str(s.ip) if s.ip else None,
                              created_at=started, last_used_at=s.created_at, expires_at=s.expires_at,
                              is_current=s.family_id == current_family))  # fmt: skip
    return out


async def revoke_session(db: AsyncSession, user_id: uuid.UUID, family_id: uuid.UUID) -> None:
    if not await repo.family_belongs(db, user_id, family_id):
        raise NotFoundError("Session not found")
    await repo.revoke_family(db, family_id, "USER_REVOKED")
