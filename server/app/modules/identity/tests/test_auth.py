import re
import time

import pyotp
import pytest

from app.core.security import current_totp
from tests import factories as f

API = f.API
RW = {"X-Requested-With": "inaiflow"}


def _code(outbox, email, tag):
    msg = outbox.last_to(email, tag)
    assert msg is not None, f"no {tag} email for {email}"
    return re.search(r"\b(\d{6})\b", msg.text).group(1)


async def _signup_verified(client, outbox, email=None, password=f.PASSWORD):
    email = email or f"{f.unique('s')}@example.com"
    r = await client.post(f"{API}/auth/signup", json={"full_name": "Sam Signup", "email": email, "password": password})
    assert r.status_code == 201 and r.json() == {"email": email, "verification_required": True}
    r = await client.post(
        f"{API}/auth/verify-email", json={"email": email, "code": _code(outbox, email, "EMAIL_VERIFY")}
    )
    assert r.status_code == 204, r.text
    return email


async def test_signup_verify_login_me(client, outbox):
    email = f"{f.unique('s')}@example.com"
    await client.post(f"{API}/auth/signup", json={"full_name": "Sam", "email": email, "password": f.PASSWORD})
    r = await client.post(f"{API}/auth/login", json={"email": email, "password": f.PASSWORD})
    assert r.status_code == 403 and r.json()["error"]["code"] == "EMAIL_NOT_VERIFIED"
    bad = await client.post(f"{API}/auth/verify-email", json={"email": email, "code": "000000"})
    assert bad.status_code == 400
    code = _code(outbox, email, "EMAIL_VERIFY")
    assert (await client.post(f"{API}/auth/verify-email", json={"email": email, "code": code})).status_code == 204
    r = await client.post(f"{API}/auth/login", json={"email": email, "password": f.PASSWORD})
    body = r.json()
    assert r.status_code == 200 and body["status"] == "OK" and body["token"]["token_type"] == "bearer"
    cookie = r.headers["set-cookie"]
    assert "if_rt=" in cookie and "HttpOnly" in cookie and "Path=/api/v1/auth" in cookie and "SameSite=strict" in cookie
    me = await client.get(f"{API}/me", headers={"Authorization": f"Bearer {body['token']['access_token']}"})
    assert me.status_code == 200 and me.json()["email"] == email and me.json()["is_email_verified"]


async def test_signup_existing_email_same_shape_and_notifies(client, outbox):
    user = await f.create_user()
    r = await client.post(f"{API}/auth/signup", json={"full_name": "X", "email": user.email, "password": f.PASSWORD})
    assert r.status_code == 201 and r.json()["verification_required"] is True
    assert outbox.last_to(user.email, "SIGNUP_EXISTING") is not None


async def test_weak_password_rejected(client):
    r = await client.post(
        f"{API}/auth/signup", json={"full_name": "X", "email": "weak@example.com", "password": "password1"}
    )
    assert r.status_code == 400 and r.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_login_generic_errors(client):
    user = await f.create_user()
    for email in (user.email, "nobody-here@example.com"):
        r = await client.post(f"{API}/auth/login", json={"email": email, "password": "Wrong-password-1"})
        assert r.status_code == 401 and r.json()["error"]["code"] == "INVALID_CREDENTIALS"


async def test_refresh_rotation_and_reuse_detection(client, outbox):
    email = await _signup_verified(client, outbox)
    r = await client.post(f"{API}/auth/login", json={"email": email, "password": f.PASSWORD})
    rt1 = client.cookies.get("if_rt")
    assert (await client.post(f"{API}/auth/refresh")).status_code == 403  # CSRF header required
    r2 = await client.post(f"{API}/auth/refresh", headers=RW)
    assert r2.status_code == 200
    rt2 = client.cookies.get("if_rt")
    assert rt2 and rt2 != rt1
    access2 = r2.json()["token"]["access_token"]
    assert (await client.get(f"{API}/me", headers={"Authorization": f"Bearer {access2}"})).status_code == 200
    # replay the rotated token -> whole family revoked
    client.cookies.set("if_rt", rt1, path="/api/v1/auth")
    assert (await client.post(f"{API}/auth/refresh", headers=RW)).status_code == 401
    client.cookies.set("if_rt", rt2, path="/api/v1/auth")
    assert (await client.post(f"{API}/auth/refresh", headers=RW)).status_code == 401
    assert (await client.get(f"{API}/me", headers={"Authorization": f"Bearer {access2}"})).status_code == 401
    assert r.status_code == 200


async def test_logout_revokes_session(client, outbox):
    email = await _signup_verified(client, outbox)
    r = await client.post(f"{API}/auth/login", json={"email": email, "password": f.PASSWORD, "remember": True})
    assert "Max-Age=2592000" in r.headers["set-cookie"]
    access = r.json()["token"]["access_token"]
    out = await client.post(f"{API}/auth/logout")
    assert out.status_code == 204 and 'if_rt=""' in out.headers["set-cookie"]
    assert (await client.get(f"{API}/me", headers={"Authorization": f"Bearer {access}"})).status_code == 401


async def test_mfa_enable_login_and_recovery_code(client, outbox):
    email = await _signup_verified(client, outbox)
    access = (await client.post(f"{API}/auth/login", json={"email": email, "password": f.PASSWORD})).json()["token"][
        "access_token"
    ]
    h = {"Authorization": f"Bearer {access}"}
    setup = (await client.post(f"{API}/me/mfa/setup", headers=h)).json()
    assert setup["otpauth_uri"].startswith("otpauth://totp/")
    assert (await client.post(f"{API}/me/mfa/enable", json={"code": "123456"}, headers=h)).status_code == 401
    codes = (await client.post(f"{API}/me/mfa/enable", json={"code": current_totp(setup["secret"])}, headers=h)).json()[
        "recovery_codes"
    ]
    assert len(codes) == 10 and all(re.fullmatch(r"[a-z0-9]{4}-[a-z0-9]{4}", c) for c in codes)

    r = await client.post(f"{API}/auth/login", json={"email": email, "password": f.PASSWORD})
    body = r.json()
    assert body["status"] == "MFA_REQUIRED" and body["token"] is None and "set-cookie" not in r.headers
    bad = await client.post(f"{API}/auth/mfa/verify", json={"mfa_token": body["mfa_token"], "code": "000000"})
    assert bad.status_code == 401 and bad.json()["error"]["code"] == "MFA_INVALID"
    replay = await client.post(
        f"{API}/auth/mfa/verify", json={"mfa_token": body["mfa_token"], "code": current_totp(setup["secret"])}
    )
    assert replay.status_code == 401  # the enable code was burned; a TOTP code works once
    next_code = pyotp.TOTP(setup["secret"]).at(time.time() + 30)
    ok = await client.post(f"{API}/auth/mfa/verify", json={"mfa_token": body["mfa_token"], "code": next_code})
    assert ok.status_code == 200 and "if_rt=" in ok.headers["set-cookie"]

    body = (await client.post(f"{API}/auth/login", json={"email": email, "password": f.PASSWORD})).json()
    rc = await client.post(f"{API}/auth/mfa/verify", json={"mfa_token": body["mfa_token"], "code": codes[0].upper()})
    assert rc.status_code == 200
    body = (await client.post(f"{API}/auth/login", json={"email": email, "password": f.PASSWORD})).json()
    again = await client.post(f"{API}/auth/mfa/verify", json={"mfa_token": body["mfa_token"], "code": codes[0]})
    assert again.status_code == 401  # single use
    # tokens issued after MFA carry mfa=true; refresh keeps it
    refreshed = await client.post(f"{API}/auth/refresh", headers=RW)
    from app.core.security import decode_access_token

    assert decode_access_token(refreshed.json()["token"]["access_token"]).mfa is True


async def test_mfa_disable_requires_password_and_code(client):
    user = await f.create_user(mfa=True)
    r = await client.post(f"{API}/me/mfa/disable", json={"password": "nope-nope-nope", "code": current_totp(user.mfa_secret)},
                          headers=user.user_headers)  # fmt: skip
    assert r.status_code == 401
    r = await client.post(f"{API}/me/mfa/disable", json={"password": f.PASSWORD, "code": current_totp(user.mfa_secret)},
                          headers=user.user_headers)  # fmt: skip
    assert r.status_code == 204
    assert (await client.get(f"{API}/me", headers=user.user_headers)).json()["mfa_enabled"] is False


async def test_login_rate_limited_after_5_failures(client):
    user = await f.create_user()
    for _ in range(5):
        r = await client.post(f"{API}/auth/login", json={"email": user.email, "password": "Wrong-password-1"})
        assert r.status_code == 401
    r = await client.post(f"{API}/auth/login", json={"email": user.email, "password": f.PASSWORD})
    assert r.status_code == 429 and r.json()["error"]["code"] == "RATE_LIMITED" and "retry-after" in r.headers


async def test_password_reset_revokes_sessions(client, outbox):
    user = await f.create_user()
    assert (await client.get(f"{API}/me", headers=user.user_headers)).status_code == 200
    assert (await client.post(f"{API}/auth/password/forgot", json={"email": user.email})).status_code == 204
    assert (await client.post(f"{API}/auth/password/forgot", json={"email": "ghost@example.com"})).status_code == 204
    code = _code(outbox, user.email, "PASSWORD_RESET")
    new_pw = "Another-Strong-Pass-7"
    r = await client.post(
        f"{API}/auth/password/reset", json={"email": user.email, "code": code, "new_password": new_pw}
    )
    assert r.status_code == 204
    assert (await client.get(f"{API}/me", headers=user.user_headers)).status_code == 401
    r = await client.post(
        f"{API}/auth/password/reset", json={"email": user.email, "code": code, "new_password": new_pw}
    )
    assert r.status_code == 400  # code consumed
    assert (await client.post(f"{API}/auth/login", json={"email": user.email, "password": new_pw})).status_code == 200


async def test_code_attempts_are_limited(client, outbox):
    email = f"{f.unique('s')}@example.com"
    await client.post(f"{API}/auth/signup", json={"full_name": "Sam", "email": email, "password": f.PASSWORD})
    code = _code(outbox, email, "EMAIL_VERIFY")
    for _ in range(5):
        assert (
            await client.post(f"{API}/auth/verify-email", json={"email": email, "code": "999999"})
        ).status_code == 400
    r = await client.post(f"{API}/auth/verify-email", json={"email": email, "code": code})
    assert r.status_code == 400  # burned after 5 wrong attempts


async def test_sessions_list_and_revoke(client):
    user = await f.create_user()
    other = await f.token_for(user.user_id, user.email)
    sessions = (await client.get(f"{API}/me/sessions", headers=user.user_headers)).json()
    assert len(sessions) == 2 and sum(s["is_current"] for s in sessions) == 1
    r = await client.delete(f"{API}/me/sessions/{other.session_id}", headers=user.user_headers)
    assert r.status_code == 204
    assert (await client.get(f"{API}/me", headers=other.user_headers)).status_code == 401
    assert (await client.get(f"{API}/me", headers=user.user_headers)).status_code == 200


async def test_change_password_keeps_current_session_only(client):
    user = await f.create_user()
    other = await f.token_for(user.user_id, user.email)
    r = await client.post(f"{API}/me/password", json={"current_password": f.PASSWORD, "new_password": "Fresh-Password-42"},
                          headers=user.user_headers)  # fmt: skip
    assert r.status_code == 204
    assert (await client.get(f"{API}/me", headers=user.user_headers)).status_code == 200
    assert (await client.get(f"{API}/me", headers=other.user_headers)).status_code == 401


async def test_me_update_and_avatar_upload(client):
    user = await f.create_user()
    r = await client.patch(
        f"{API}/me", json={"full_name": "Renamed", "mobile": "+91 90000 00000"}, headers=user.user_headers
    )
    assert r.status_code == 200 and r.json()["full_name"] == "Renamed"
    t = (await client.post(f"{API}/me/files/upload-url", json={"purpose": "AVATAR", "content_type": "image/png", "size_bytes": 8},
                           headers=user.user_headers)).json()  # fmt: skip
    assert t["method"] == "PUT" and t["storage_key"].startswith(f"users/{user.user_id}/avatar/")
    r = await client.patch(f"{API}/me", json={"avatar_storage_key": t["storage_key"]}, headers=user.user_headers)
    assert r.status_code == 400  # not uploaded yet
    put = await client.put(t["upload_url"], content=b"\x89PNG1234", headers=t["headers"])
    assert put.status_code == 204
    r = await client.patch(f"{API}/me", json={"avatar_storage_key": t["storage_key"]}, headers=user.user_headers)
    assert r.status_code == 200 and "/storage/local/" in r.json()["avatar_url"]
    got = await client.get(r.json()["avatar_url"])
    assert got.status_code == 200 and got.content == b"\x89PNG1234"
    bad = await client.post(f"{API}/me/files/upload-url", json={"purpose": "AVATAR", "content_type": "application/x-sh",
                                                               "size_bytes": 8}, headers=user.user_headers)  # fmt: skip
    assert bad.status_code == 415


@pytest.mark.parametrize("path", ["/auth/oauth/google/start"])
async def test_google_oauth_disabled_404(client, path):
    assert (await client.get(f"{API}{path}")).status_code == 404


async def test_google_callback_disabled_redirects(client):
    r = await client.get(f"{API}/auth/oauth/google/callback", params={"code": "x", "state": "y"})
    assert r.status_code == 302 and r.headers["location"].endswith("/login?error=oauth_disabled")


async def test_unauthenticated_and_suspended(client):
    assert (await client.get(f"{API}/me")).json()["error"]["code"] == "UNAUTHENTICATED"
    user = await f.create_user(suspended=True)
    r = await client.get(f"{API}/me", headers=user.user_headers)
    assert r.status_code == 403 and r.json()["error"]["code"] == "ACCOUNT_SUSPENDED"
