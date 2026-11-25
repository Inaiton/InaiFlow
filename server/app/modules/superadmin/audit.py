"""Thin wrapper over ``superadmin.interface.write_platform_audit``: sanitizes the IP and records the typed reason."""

from __future__ import annotations

import dataclasses
import ipaddress
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import AdminPrincipal
from app.modules.superadmin.interface import write_platform_audit


def _valid_ip(ip: str | None) -> str | None:
    if not ip:
        return None
    try:
        return str(ipaddress.ip_address(ip))
    except ValueError:
        return None


async def audit(
    db: AsyncSession, admin: AdminPrincipal, action: str, target_type: str, target_id: uuid.UUID | None, *,
    before: Any = None, after: Any = None, reason: str | None = None,
) -> None:  # fmt: skip
    """Every admin mutation calls this. The reason is stored inside ``after_state`` (``{"reason": ...}``)."""
    if reason is not None:
        after = {**(after if isinstance(after, dict) else {} if after is None else {"value": after}), "reason": reason}
    principal = dataclasses.replace(admin, ip=_valid_ip(admin.ip))
    await write_platform_audit(db, principal, action, target_type, target_id, before=before, after=after)
