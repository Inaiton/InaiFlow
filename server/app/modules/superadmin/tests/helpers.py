"""Admin test helpers: create platform admins directly, sign in through the real auth flow."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

import httpx
from sqlalchemy import text

from app.core.security import current_totp, encrypt_secret, hash_password, new_totp_secret
from tests import factories as f

API = f.API
PASSWORD = "Admin-Correct-Horse-42"


@dataclass
class AdminActor:
    id: uuid.UUID
    email: str
    role: str
    password: str
    secret: str | None
    token: str = ""

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}


async def make_admin(role: str = "SUPERADMIN", *, mfa: bool = True, must_change: bool = False,
                     active: bool = True) -> AdminActor:  # fmt: skip
    email = f"{f.unique('adm')}@example.com"
    secret = new_totp_secret() if mfa else None
    async with f.session() as s, s.begin():
        aid = (
            await s.execute(
                text(
                    "INSERT INTO platform_admins (email, password_hash, full_name, role, is_active, mfa_secret, "
                    "mfa_enabled, must_change_password) VALUES (:e, :h, 'Test Admin', :r, :act, :sec, :mfa, :mc) "
                    "RETURNING id"
                ),
                {
                    "e": email,
                    "h": await hash_password(PASSWORD),
                    "r": role,
                    "act": active,
                    "sec": encrypt_secret(secret) if secret else None,
                    "mfa": mfa,
                    "mc": must_change,
                },
            )  # fmt: skip
        ).scalar_one()
    return AdminActor(aid, email, role, PASSWORD, secret)


async def sign_in(client: httpx.AsyncClient, admin: AdminActor) -> AdminActor:
    r = await client.post(f"{API}/admin/auth/login", json={"email": admin.email, "password": admin.password})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "MFA_REQUIRED"
    r = await client.post(f"{API}/admin/auth/mfa/verify",
                          json={"mfa_token": r.json()["mfa_token"], "code": current_totp(admin.secret)})  # fmt: skip
    assert r.status_code == 200, r.text
    admin.token = r.json()["token"]["access_token"]
    return admin


async def admin_with_token(client: httpx.AsyncClient, role: str = "SUPERADMIN") -> AdminActor:
    return await sign_in(client, await make_admin(role))


def secret_from_uri(uri: str) -> str:
    from urllib.parse import parse_qs, urlsplit

    return parse_qs(urlsplit(uri).query)["secret"][0]


async def audit_actions(target_id: uuid.UUID) -> list[str]:
    rows = await f.sql("SELECT action FROM platform_audit_logs WHERE target_id = :t ORDER BY created_at", t=target_id)
    return [r[0] for r in rows]
