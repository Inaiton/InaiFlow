"""Test factories. Everything is unique per call, so tests never need cleanup.

owner = await org_with_owner(client)                       # real POST /organizations (full seeding)
acct = await add_member(owner.org_id, "ACCOUNTANT")         # direct insert + access token
r = await client.get("/api/v1/organization/members", headers=acct.headers)
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import select, text, update

from app.core.db import get_sessionmaker
from app.core.security import (
    create_access_token,
    encrypt_secret,
    hash_password,
    hash_token,
    new_refresh_token,
    new_totp_secret,
)
from app.modules.identity.models import User, UserSession
from app.modules.organization.models import Organization, OrgMembership
from app.modules.rbac.models import OrgRole

PASSWORD = "Correct-Horse-Battery-9"
API = "/api/v1"


def unique(prefix: str = "t") -> str:
    return f"{prefix}{uuid.uuid4().hex[:10]}"


@dataclass
class Actor:
    user_id: uuid.UUID
    email: str
    token: str
    password: str = PASSWORD
    org_id: uuid.UUID | None = None
    membership_id: uuid.UUID | None = None
    role_code: str | None = None
    session_id: uuid.UUID | None = None
    mfa_secret: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def headers(self) -> dict[str, str]:
        h = {"Authorization": f"Bearer {self.token}"}
        if self.org_id:
            h["X-Organization-ID"] = str(self.org_id)
        return h

    @property
    def user_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

    def in_org(self, org_id: uuid.UUID) -> Actor:
        return replace(self, org_id=org_id)


def session():  # noqa: ANN201
    """Platform (connection-user) session for direct setup writes: ``async with session() as s, s.begin():``."""
    return get_sessionmaker()()


async def create_user(
    *, email: str | None = None, password: str = PASSWORD, full_name: str = "Test User", verified: bool = True,
    mfa: bool = False, suspended: bool = False,
) -> Actor:  # fmt: skip
    email = (email or f"{unique('u')}@example.com").lower()
    secret = new_totp_secret() if mfa else None
    async with session() as s, s.begin():
        user = User(email=email, full_name=full_name, password_hash=await hash_password(password),
                    is_email_verified=verified, mfa_enabled=mfa, is_suspended=suspended,
                    mfa_secret=encrypt_secret(secret) if secret else None, oauth_provider="LOCAL")  # fmt: skip
        s.add(user)
        await s.flush()
        user_id = user.id
    actor = await token_for(user_id, email, mfa=mfa)
    actor.password, actor.mfa_secret = password, secret
    return actor


async def token_for(user_id: uuid.UUID, email: str, *, mfa: bool = False) -> Actor:
    family = uuid.uuid4()
    async with session() as s, s.begin():
        s.add(UserSession(user_id=user_id, family_id=family, token_hash=hash_token(new_refresh_token()),
                          expires_at=datetime.now(UTC) + timedelta(days=1)))  # fmt: skip
    token, _ = create_access_token(user_id=user_id, session_id=family, email=email, mfa=mfa)
    return Actor(user_id=user_id, email=email, token=token, session_id=family)


def org_payload(**overrides: Any) -> dict[str, Any]:
    body = {
        "legal_name": "Precision Components Pvt Ltd",
        "workspace_slug": unique("org-"),
        "address_line1": "12 Industrial Estate",
        "city": "Coimbatore",
        "state_code": "33",
        "pincode": "641021",
        "fy_begins_from": "2026-04-01",
        "books_beginning_from": "2026-04-01",
        "contact_email": "accounts@example.com",
        "contact_phone": "+91 98400 00000",
        "gst_reg_type": "REGULAR",
        "gstin": "33ABCDE1234F1Z5",
        "industry_type": "Manufacturing",
    }
    body.update(overrides)
    return body


async def org_with_owner(client: httpx.AsyncClient, **org_overrides: Any) -> Actor:
    owner = await create_user(full_name="Olivia Owner")
    r = await client.post(f"{API}/organizations", json=org_payload(**org_overrides), headers=owner.user_headers)
    assert r.status_code == 201, r.text
    org_id = uuid.UUID(r.json()["org_id"])
    async with session() as s:
        mid = (await s.execute(select(OrgMembership.id).where(OrgMembership.org_id == org_id))).scalar_one()
    owner.org_id, owner.membership_id, owner.role_code = org_id, mid, "ORG_OWNER"
    owner.extra["org"] = r.json()
    return owner


async def role_id(org_id: uuid.UUID, role_code: str) -> uuid.UUID:
    async with session() as s:
        return (
            await s.execute(select(OrgRole.id).where(OrgRole.org_id == org_id, OrgRole.role_code == role_code))
        ).scalar_one()


async def add_member(
    org_id: uuid.UUID, role_code: str = "ACCOUNTANT", *, user: Actor | None = None, mfa: bool = False,
    access_expires_at: datetime | None = None, status: str = "ACTIVE",
) -> Actor:  # fmt: skip
    actor = user or await create_user(mfa=mfa, full_name=f"{role_code.title()} Person")
    rid = await role_id(org_id, role_code)
    async with session() as s, s.begin():
        m = OrgMembership(org_id=org_id, user_id=actor.user_id, role_id=rid, status=status,
                          access_expires_at=access_expires_at)  # fmt: skip
        s.add(m)
        await s.flush()
        actor.membership_id = m.id
    if mfa and user is None:
        actor = replace(actor, token=(await token_for(actor.user_id, actor.email, mfa=True)).token)
    actor.org_id, actor.role_code = org_id, role_code
    return actor


async def set_org(org_id: uuid.UUID, **values: Any) -> None:
    async with session() as s, s.begin():
        await s.execute(update(Organization).where(Organization.id == org_id).values(**values))


async def sql(query: str, **params: Any) -> list[Any]:
    async with session() as s, s.begin():
        res = await s.execute(text(query), params)
        return list(res.all()) if res.returns_rows else []


TODAY = date.today
