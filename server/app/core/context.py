"""Request principals and the tenant context passed to every service function."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime

from app.core.permissions import ALL_PERMISSION_KEYS, at_least


@dataclass(frozen=True, slots=True)
class Impersonation:
    session_id: uuid.UUID
    admin_id: uuid.UUID
    admin_name: str
    org_id: uuid.UUID
    mode: str  # READ_ONLY | FULL_SUPPORT
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class Principal:
    """Authenticated caller of user-audience routes. For impersonation tokens ``user_id`` = admin id."""

    user_id: uuid.UUID
    session_id: uuid.UUID
    email: str
    mfa: bool
    ip: str | None = None
    user_agent: str | None = None
    impersonation: Impersonation | None = None


@dataclass(frozen=True, slots=True)
class AdminPrincipal:
    admin_id: uuid.UUID
    session_id: uuid.UUID
    email: str
    role: str
    ip: str | None = None
    user_agent: str | None = None


@dataclass(frozen=True, slots=True)
class TenantContext:
    """Everything a service needs about *who* acts in *which* org.

    ``user_id`` is the acting user (for impersonation: the org owner, so ``created_by`` FKs stay valid; the
    real actor is ``actor_type='PLATFORM_ADMIN'`` / ``actor_id`` and is what audit rows record).
    ``user_id`` is None for SYSTEM contexts (cron).
    """

    org_id: uuid.UUID
    user_id: uuid.UUID | None
    membership_id: uuid.UUID | None
    role_code: str
    role_id: uuid.UUID | None
    is_external: bool
    is_owner: bool
    permissions: dict[str, str]
    mfa: bool = False
    impersonation: Impersonation | None = None
    ip: str | None = None
    user_agent: str | None = None
    actor_type: str = "USER"  # USER | SYSTEM | PLATFORM_ADMIN
    actor_id: uuid.UUID | None = None
    role_name: str = ""
    extra: dict = field(default_factory=dict)

    def level(self, key: str) -> str:
        if self.is_owner:
            return "FULL"
        return self.permissions.get(key, "NONE")

    def has(self, key: str, level: str) -> bool:
        return at_least(self.level(key), level)

    @property
    def audit_user_id(self) -> uuid.UUID | None:
        return self.user_id if self.actor_type == "USER" else None

    def with_role(self, **changes: object) -> TenantContext:
        return replace(self, **changes)  # type: ignore[arg-type]

    @classmethod
    def system(cls, org_id: uuid.UUID, *, user_id: uuid.UUID | None = None) -> TenantContext:
        """Context for cron/background work and org seeding (all permissions)."""
        return cls(
            org_id=org_id,
            user_id=user_id,
            membership_id=None,
            role_code="SYSTEM",
            role_id=None,
            is_external=False,
            is_owner=False,
            permissions=dict.fromkeys(ALL_PERMISSION_KEYS, "FULL"),
            actor_type="SYSTEM",
            role_name="System",
        )
