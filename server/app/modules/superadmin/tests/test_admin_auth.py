"""Admin auth state machine: setup -> verify, forced password change, MFA required, refresh rotation/reuse,
IP allowlist, inactive admins, CLI bootstrap."""

import pytest

from app.core.config import get_settings
from app.core.security import current_totp

from . import helpers as h

API = h.API


async def test_first_login_password_change_and_mfa_setup(client):
    admin = await h.make_admin(mfa=False, must_change=True)  # what `cli create-superadmin` produces
    r = await client.post(f"{API}/admin/auth/login", json={"email": admin.email, "password": admin.password})
    body = r.json()
    assert r.status_code == 200 and body["status"] == "PASSWORD_CHANGE_REQUIRED"
    assert body["otpauth_uri"].startswith("otpauth://totp/")
    secret = h.secret_from_uri(body["otpauth_uri"])
    # retrying the login keeps the same pending secret
    r2 = await client.post(f"{API}/admin/auth/login", json={"email": admin.email, "password": admin.password})
    assert h.secret_from_uri(r2.json()["otpauth_uri"]) == secret
    token = r2.json()["mfa_token"]
    stored = (await h.f.sql("SELECT mfa_secret, mfa_enabled FROM platform_admins WHERE id=:i", i=admin.id))[0]
    assert stored[0] and secret not in stored[0] and stored[1] is False  # encrypted, not yet enrolled

    r = await client.post(f"{API}/admin/auth/mfa/verify", json={"mfa_token": token, "code": current_totp(secret)})
    assert r.status_code == 400  # new_password required
    r = await client.post(f"{API}/admin/auth/mfa/verify",
                          json={"mfa_token": token, "code": current_totp(secret), "new_password": "short"})  # fmt: skip
    assert r.status_code == 400
    r = await client.post(f"{API}/admin/auth/mfa/verify",
                          json={"mfa_token": token, "code": "000000", "new_password": "A-Brand-New-Passw0rd"})  # fmt: skip
    assert r.status_code == 401 and r.json()["error"]["code"] == "MFA_INVALID"
    r = await client.post(f"{API}/admin/auth/mfa/verify",
                          json={"mfa_token": token, "code": current_totp(secret), "new_password": "A-Brand-New-Passw0rd"})  # fmt: skip
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["admin"]["mfa_enabled"] is True and out["token"]["token_type"] == "bearer"
    cookie = r.headers["set-cookie"]
    assert "if_art=" in cookie and "HttpOnly" in cookie and "Path=/api/v1/admin/auth" in cookie
    assert "samesite=strict" in cookie.lower()
    me = await client.get(f"{API}/admin/me", headers={"Authorization": f"Bearer {out['token']['access_token']}"})
    assert me.status_code == 200 and me.json()["email"] == admin.email

    # old password is gone; new one -> plain MFA_REQUIRED without a setup URI
    r = await client.post(f"{API}/admin/auth/login", json={"email": admin.email, "password": admin.password})
    assert r.status_code == 401
    r = await client.post(f"{API}/admin/auth/login", json={"email": admin.email, "password": "A-Brand-New-Passw0rd"})
    assert r.json()["status"] == "MFA_REQUIRED" and r.json()["otpauth_uri"] is None
    assert "ADMIN_LOGIN" in await h.audit_actions(admin.id)


async def test_mfa_setup_required_without_password_change(client):
    admin = await h.make_admin(mfa=False)
    r = await client.post(f"{API}/admin/auth/login", json={"email": admin.email, "password": admin.password})
    assert r.json()["status"] == "MFA_SETUP_REQUIRED" and r.json()["otpauth_uri"]
    secret = h.secret_from_uri(r.json()["otpauth_uri"])
    r = await client.post(f"{API}/admin/auth/mfa/verify",
                          json={"mfa_token": r.json()["mfa_token"], "code": current_totp(secret)})  # fmt: skip
    assert r.status_code == 200 and r.json()["admin"]["mfa_enabled"] is True


async def test_generic_errors_and_inactive(client):
    admin = await h.make_admin()
    bad = await client.post(f"{API}/admin/auth/login", json={"email": admin.email, "password": "wrong-password-1"})
    unknown = await client.post(f"{API}/admin/auth/login", json={"email": "nobody@x.io", "password": "wrong-pass-12"})
    assert bad.status_code == unknown.status_code == 401
    assert bad.json()["error"] == unknown.json()["error"]
    inactive = await h.make_admin(active=False)
    r = await client.post(f"{API}/admin/auth/login", json={"email": inactive.email, "password": inactive.password})
    assert r.status_code == 403


async def test_user_tokens_are_not_admin_tokens(client, owner):
    r = await client.get(f"{API}/admin/me", headers=owner.user_headers)
    assert r.status_code == 401


async def test_login_rate_limited(client):
    admin = await h.make_admin()
    for _ in range(5):
        await client.post(f"{API}/admin/auth/login", json={"email": admin.email, "password": "wrong-password-1"})
    r = await client.post(f"{API}/admin/auth/login", json={"email": admin.email, "password": admin.password})
    assert r.status_code == 429


async def test_refresh_rotation_and_reuse_detection(client):
    admin = await h.admin_with_token(client)
    first = client.cookies.get("if_art", path="/api/v1/admin/auth")
    assert first
    r = await client.post(f"{API}/admin/auth/refresh")
    assert r.status_code == 403  # CSRF header missing
    hdr = {"X-Requested-With": "inaiflow"}
    r = await client.post(f"{API}/admin/auth/refresh", headers=hdr)
    assert r.status_code == 200, r.text
    second = client.cookies.get("if_art", path="/api/v1/admin/auth")
    assert second and second != first
    new_token = r.json()["token"]["access_token"]
    # replay the rotated token -> whole family revoked
    client.cookies.clear()
    client.cookies.set("if_art", first)
    r = await client.post(f"{API}/admin/auth/refresh", headers=hdr)
    assert r.status_code == 401
    client.cookies.clear()
    client.cookies.set("if_art", second)
    r = await client.post(f"{API}/admin/auth/refresh", headers=hdr)
    assert r.status_code == 401
    me = await client.get(f"{API}/admin/me", headers={"Authorization": f"Bearer {new_token}"})
    assert me.status_code == 401
    assert admin.id


async def test_logout_revokes(client):
    admin = await h.admin_with_token(client)
    r = await client.post(f"{API}/admin/auth/logout")
    assert r.status_code == 204
    assert (await client.get(f"{API}/admin/me", headers=admin.headers)).status_code == 401


async def test_ip_allowlist(client, monkeypatch: pytest.MonkeyPatch):
    admin = await h.admin_with_token(client)
    monkeypatch.setattr(get_settings(), "ADMIN_IP_ALLOWLIST", "192.0.2.0/24")
    for r in (
        await client.get(f"{API}/admin/me", headers=admin.headers),
        await client.post(f"{API}/admin/auth/login", json={"email": admin.email, "password": admin.password}),
        await client.post(f"{API}/admin/auth/refresh", headers={"X-Requested-With": "inaiflow"}),
    ):
        assert r.status_code == 403 and r.json()["error"]["code"] == "IP_NOT_ALLOWED"
    monkeypatch.setattr(get_settings(), "ADMIN_IP_ALLOWLIST", "10.0.0.0/8, 192.0.2.0/24")
    assert (await client.get(f"{API}/admin/me", headers=admin.headers)).status_code == 200


async def test_cli_created_admin_can_sign_in(client, capsys):
    from app.cli import create_superadmin

    email = f"{h.f.unique('cli')}@example.com"
    await create_superadmin(email, "CLI Admin", "SUPERADMIN")
    password = capsys.readouterr().out.split("One-time password: ")[1].split()[0]
    r = await client.post(f"{API}/admin/auth/login", json={"email": email, "password": password})
    assert r.json()["status"] == "PASSWORD_CHANGE_REQUIRED" and r.json()["otpauth_uri"]
