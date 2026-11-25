"""Public API of the identity module. Works under the RLS app role too (selects only granted columns)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_sessionmaker
from app.core.security import verify_password
from app.modules.identity.models import User
from app.modules.identity.schemas import TokenOut as TokenOut  # re-exported for the admin auth envelope (S5)


@dataclass(frozen=True, slots=True)
class UserBrief:
    id: uuid.UUID
    email: str
    full_name: str
    is_email_verified: bool
    mfa_enabled: bool
    professional_reg_no: str | None
    is_suspended: bool


_COLS = (User.id, User.email, User.full_name, User.is_email_verified, User.mfa_enabled, User.professional_reg_no,
         User.is_suspended)  # fmt: skip


async def user_briefs(db: AsyncSession, user_ids: list[uuid.UUID]) -> dict[uuid.UUID, UserBrief]:
    ids = list({i for i in user_ids if i})
    if not ids:
        return {}
    rows = await db.execute(select(*_COLS).where(User.id.in_(ids)))
    return {r.id: UserBrief(*r) for r in rows.all()}


async def user_brief(db: AsyncSession, user_id: uuid.UUID) -> UserBrief | None:
    return (await user_briefs(db, [user_id])).get(user_id)


async def user_brief_by_email(db: AsyncSession, email: str) -> UserBrief | None:
    row = (await db.execute(select(*_COLS).where(User.email == email.strip().lower()))).first()
    return UserBrief(*row) if row else None


async def check_password(user_id: uuid.UUID, password: str) -> bool:
    """Re-check a user's password (e.g. transfer ownership). Uses its own platform session because the
    tenant role cannot read password hashes."""
    async with get_sessionmaker()() as s:
        pw_hash = (await s.execute(select(User.password_hash).where(User.id == user_id))).scalar()
    return await verify_password(pw_hash, password)


# ---------------------------------------------------------------- platform-admin operations (added by S5)
# Platform session only (connection user): the RLS app role cannot update users / user_sessions.
async def active_session_count(db: AsyncSession, user_id: uuid.UUID) -> int:
    """Number of live logical sessions (refresh families) of a user."""
    from app.modules.identity import repository as _repo

    return len(await _repo.active_sessions(db, user_id))


async def _user_or_none(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    from app.modules.identity import repository as _repo

    return await _repo.user_by_id(db, user_id)


async def set_user_suspended(db: AsyncSession, user_id: uuid.UUID, suspended: bool) -> UserBrief | None:
    """Suspend / unsuspend a user. Suspension also revokes every session. None if the user does not exist."""
    from datetime import UTC, datetime

    from app.modules.identity import repository as _repo

    user = await _user_or_none(db, user_id)
    if user is None:
        return None
    user.is_suspended, user.updated_at = suspended, datetime.now(UTC)
    if suspended:
        await _repo.revoke_user_sessions(db, user_id, "SUSPENDED")
    await db.flush()
    return await user_brief(db, user_id)


async def reset_user_mfa(db: AsyncSession, user_id: uuid.UUID) -> UserBrief | None:
    """Disable TOTP, clear the secret and all recovery codes (the user re-enrolls from /me/security)."""
    from datetime import UTC, datetime

    from app.modules.identity import repository as _repo

    user = await _user_or_none(db, user_id)
    if user is None:
        return None
    user.mfa_enabled, user.mfa_secret, user.updated_at = False, None, datetime.now(UTC)
    await _repo.delete_recovery_codes(db, user_id)
    await db.flush()
    return await user_brief(db, user_id)


async def mark_email_verified(db: AsyncSession, user_id: uuid.UUID) -> UserBrief | None:
    from datetime import UTC, datetime

    user = await _user_or_none(db, user_id)
    if user is None:
        return None
    user.is_email_verified, user.updated_at = True, datetime.now(UTC)
    await db.flush()
    return await user_brief(db, user_id)


async def revoke_all_sessions(db: AsyncSession, user_id: uuid.UUID, reason: str = "ADMIN_REVOKED") -> int:
    """Revoke every live session of a user; returns how many logical sessions were live."""
    from app.modules.identity import repository as _repo

    count = await active_session_count(db, user_id)
    await _repo.revoke_user_sessions(db, user_id, reason[:30])
    await db.flush()
    return count
