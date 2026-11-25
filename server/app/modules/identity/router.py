from __future__ import annotations

import uuid
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Header, Query, Request, Response, status
from fastapi.responses import RedirectResponse

from app.core.config import get_settings
from app.core.deps import DB, CurrentUser, client_ip, user_agent
from app.core.errors import ForbiddenError
from app.core.schemas import UploadTicket
from app.modules.identity import service
from app.modules.identity.schemas import (
    EmailIn,
    LoginIn,
    LoginOut,
    LoginSuccessOut,
    MeFileUploadIn,
    MeOut,
    MeUpdateIn,
    MfaCodeIn,
    MfaDisableIn,
    MfaSetupOut,
    MfaVerifyIn,
    PasswordChangeIn,
    PasswordResetIn,
    RecoveryCodesOut,
    SessionOut,
    SignupIn,
    SignupOut,
    VerifyEmailIn,
)

REFRESH_COOKIE = "if_rt"
COOKIE_PATH = "/api/v1/auth"
OAUTH_COOKIE = "if_oauth"

auth_router = APIRouter(prefix="/auth", tags=["auth"])
me_router = APIRouter(prefix="/me", tags=["me"])
NO_CONTENT = status.HTTP_204_NO_CONTENT


def _set_refresh(response: Response, issued: service.Issued) -> None:
    s = get_settings()
    days = s.REFRESH_TTL_REMEMBER_DAYS if issued.remember else s.REFRESH_TTL_DAYS
    response.set_cookie(REFRESH_COOKIE, issued.refresh_token, max_age=days * 86400, path=COOKIE_PATH,
                        httponly=True, secure=s.cookie_secure, samesite="strict")  # fmt: skip


def _clear_refresh(response: Response) -> None:
    response.delete_cookie(REFRESH_COOKIE, path=COOKIE_PATH, httponly=True, secure=get_settings().cookie_secure,
                           samesite="strict")  # fmt: skip


@auth_router.post("/signup", response_model=SignupOut, status_code=status.HTTP_201_CREATED)
async def signup(body: SignupIn, db: DB) -> SignupOut:
    return await service.signup(db, body)


@auth_router.post("/verify-email", status_code=NO_CONTENT)
async def verify_email(body: VerifyEmailIn, db: DB) -> Response:
    await service.verify_email(db, body.email, body.code)
    return Response(status_code=NO_CONTENT)


@auth_router.post("/resend-verification", status_code=NO_CONTENT)
async def resend_verification(body: EmailIn, db: DB) -> Response:
    await service.resend_verification(db, body.email)
    return Response(status_code=NO_CONTENT)


@auth_router.post("/login", response_model=LoginOut)
async def login(body: LoginIn, request: Request, response: Response, db: DB) -> LoginOut:
    out, issued = await service.login(db, body, client_ip(request), user_agent(request))
    if issued:
        _set_refresh(response, issued)
    return out


@auth_router.post("/mfa/verify", response_model=LoginSuccessOut)
async def mfa_verify(body: MfaVerifyIn, request: Request, response: Response, db: DB) -> LoginSuccessOut:
    issued = await service.verify_mfa(db, body.mfa_token, body.code, client_ip(request), user_agent(request))
    _set_refresh(response, issued)
    return issued.body


@auth_router.post("/refresh", response_model=LoginSuccessOut)
async def refresh(
    request: Request, response: Response, db: DB,
    x_requested_with: Annotated[str | None, Header(alias="X-Requested-With")] = None,
) -> LoginSuccessOut:  # fmt: skip
    if x_requested_with != "inaiflow":
        raise ForbiddenError("Missing X-Requested-With: inaiflow")
    issued = await service.refresh(db, request.cookies.get(REFRESH_COOKIE), client_ip(request), user_agent(request))
    _set_refresh(response, issued)
    return issued.body


@auth_router.post("/logout", status_code=NO_CONTENT)
async def logout(request: Request, db: DB) -> Response:
    await service.logout(db, request.cookies.get(REFRESH_COOKIE))
    response = Response(status_code=NO_CONTENT)
    _clear_refresh(response)
    return response


@auth_router.post("/password/forgot", status_code=NO_CONTENT)
async def forgot(body: EmailIn, db: DB) -> Response:
    await service.forgot_password(db, body.email)
    return Response(status_code=NO_CONTENT)


@auth_router.post("/password/reset", status_code=NO_CONTENT)
async def reset(body: PasswordResetIn, db: DB) -> Response:
    await service.reset_password(db, body)
    return Response(status_code=NO_CONTENT)


@auth_router.get("/oauth/google/start", status_code=status.HTTP_302_FOUND, response_class=RedirectResponse)
async def google_start(redirect_to: str | None = None) -> RedirectResponse:
    url, cookie = service.google_start(redirect_to)
    resp = RedirectResponse(url, status_code=status.HTTP_302_FOUND)
    resp.set_cookie(OAUTH_COOKIE, cookie, max_age=600, path=COOKIE_PATH, httponly=True,
                    secure=get_settings().cookie_secure, samesite="lax")  # fmt: skip
    return resp


@auth_router.get("/oauth/google/callback", status_code=status.HTTP_302_FOUND, response_class=RedirectResponse)
async def google_callback(request: Request, db: DB, code: str = Query(), state: str = Query()) -> RedirectResponse:
    """Plan §7.6: success -> /auth/callback (refresh cookie set); failure -> /login?error=oauth_failed|oauth_disabled."""
    web = get_settings().PUBLIC_USER_WEB_URL.rstrip("/")
    if not get_settings().google_enabled:
        return RedirectResponse(f"{web}/login?error=oauth_disabled", status_code=302)
    try:
        issued, redirect_to = await service.google_callback(
            db, code, state, request.cookies.get(OAUTH_COOKIE), client_ip(request), user_agent(request)
        )
    except Exception:  # noqa: BLE001 - any failure is reported to the web app generically
        resp = RedirectResponse(f"{web}/login?error=oauth_failed", status_code=302)
        resp.delete_cookie(OAUTH_COOKIE, path=COOKIE_PATH)
        return resp
    resp = RedirectResponse(f"{web}/auth/callback?{urlencode({'next': redirect_to})}", status_code=302)
    _set_refresh(resp, issued)
    resp.delete_cookie(OAUTH_COOKIE, path=COOKIE_PATH)
    return resp


# ---------------------------------------------------------------- /me
@me_router.get("", response_model=MeOut)
async def get_me(user: CurrentUser, db: DB) -> MeOut:
    return await service.get_me(db, user.user_id)


@me_router.patch("", response_model=MeOut)
async def update_me(body: MeUpdateIn, user: CurrentUser, db: DB) -> MeOut:
    return await service.update_me(db, user.user_id, body)


@me_router.post("/files/upload-url", response_model=UploadTicket)
async def me_upload_url(body: MeFileUploadIn, user: CurrentUser) -> UploadTicket:
    return await service.me_upload_url(user.user_id, body)


@me_router.post("/password", status_code=NO_CONTENT)
async def change_password(body: PasswordChangeIn, user: CurrentUser, db: DB) -> Response:
    await service.change_password(db, user.user_id, user.session_id, body)
    return Response(status_code=NO_CONTENT)


@me_router.post("/mfa/setup", response_model=MfaSetupOut)
async def mfa_setup(user: CurrentUser, db: DB) -> MfaSetupOut:
    return await service.mfa_setup(db, user.user_id)


@me_router.post("/mfa/enable", response_model=RecoveryCodesOut)
async def mfa_enable(body: MfaCodeIn, user: CurrentUser, db: DB) -> RecoveryCodesOut:
    return await service.mfa_enable(db, user.user_id, user.session_id, body.code)


@me_router.post("/mfa/disable", status_code=NO_CONTENT)
async def mfa_disable(body: MfaDisableIn, user: CurrentUser, db: DB) -> Response:
    await service.mfa_disable(db, user.user_id, body.password, body.code)
    return Response(status_code=NO_CONTENT)


@me_router.post("/mfa/recovery-codes", response_model=RecoveryCodesOut)
async def mfa_recovery_codes(body: MfaCodeIn, user: CurrentUser, db: DB) -> RecoveryCodesOut:
    return await service.mfa_regenerate_codes(db, user.user_id, body.code)


@me_router.get("/sessions", response_model=list[SessionOut])
async def list_sessions(user: CurrentUser, db: DB) -> list[SessionOut]:
    return await service.list_sessions(db, user.user_id, user.session_id)


@me_router.delete("/sessions/{session_id}", status_code=NO_CONTENT)
async def revoke_session(session_id: uuid.UUID, user: CurrentUser, db: DB) -> Response:
    await service.revoke_session(db, user.user_id, session_id)
    return Response(status_code=NO_CONTENT)
