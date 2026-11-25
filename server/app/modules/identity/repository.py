"""Identity data access (connection-user session; never commits)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.identity.models import AuthOneTimeCode, User, UserMfaRecoveryCode, UserSession


async def user_by_email(db: AsyncSession, email: str) -> User | None:
    return (await db.execute(select(User).where(User.email == email.lower()))).scalar_one_or_none()


async def user_by_id(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    return await db.get(User, user_id)


async def user_by_oauth(db: AsyncSession, provider: str, subject: str) -> User | None:
    return (
        await db.execute(select(User).where(User.oauth_provider == provider, User.oauth_subject_id == subject))
    ).scalar_one_or_none()


async def add(db: AsyncSession, obj: object) -> None:
    db.add(obj)
    await db.flush()


async def latest_code(db: AsyncSession, email: str, purpose: str) -> AuthOneTimeCode | None:
    return (
        await db.execute(
            select(AuthOneTimeCode)
            .where(
                AuthOneTimeCode.email == email.lower(),
                AuthOneTimeCode.purpose == purpose,
                AuthOneTimeCode.subject_type == "USER",
                AuthOneTimeCode.consumed_at.is_(None),
                AuthOneTimeCode.expires_at > func.now(),
            )
            .order_by(AuthOneTimeCode.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def invalidate_codes(db: AsyncSession, email: str, purpose: str) -> None:
    await db.execute(
        update(AuthOneTimeCode)
        .where(
            AuthOneTimeCode.email == email.lower(),
            AuthOneTimeCode.purpose == purpose,
            AuthOneTimeCode.consumed_at.is_(None),
        )  # fmt: skip
        .values(consumed_at=func.now())
    )


async def session_by_hash(db: AsyncSession, token_hash: str) -> UserSession | None:
    return (await db.execute(select(UserSession).where(UserSession.token_hash == token_hash))).scalar_one_or_none()


async def revoke_family(db: AsyncSession, family_id: uuid.UUID, reason: str) -> None:
    await db.execute(
        update(UserSession)
        .where(UserSession.family_id == family_id, UserSession.revoked_at.is_(None))
        .values(revoked_at=func.now(), revoke_reason=reason)
    )


async def revoke_user_sessions(
    db: AsyncSession, user_id: uuid.UUID, reason: str, except_family: uuid.UUID | None = None
) -> None:
    stmt = update(UserSession).where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
    if except_family is not None:
        stmt = stmt.where(UserSession.family_id != except_family)
    await db.execute(stmt.values(revoked_at=func.now(), revoke_reason=reason))


async def active_sessions(db: AsyncSession, user_id: uuid.UUID) -> list[tuple[UserSession, datetime]]:
    """Active head row per family with the family's first created_at."""
    first = (
        select(UserSession.family_id, func.min(UserSession.created_at).label("started"))
        .where(UserSession.user_id == user_id)
        .group_by(UserSession.family_id)
        .subquery()
    )
    rows = await db.execute(
        select(UserSession, first.c.started)
        .join(first, first.c.family_id == UserSession.family_id)
        .where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None), UserSession.expires_at > func.now())
        .order_by(UserSession.last_used_at.desc())
    )
    return [(r[0], r[1]) for r in rows.all()]


async def family_belongs(db: AsyncSession, user_id: uuid.UUID, family_id: uuid.UUID) -> bool:
    return (
        await db.execute(
            select(UserSession.id).where(UserSession.user_id == user_id, UserSession.family_id == family_id).limit(1)
        )
    ).first() is not None


async def recovery_codes(db: AsyncSession, user_id: uuid.UUID) -> list[UserMfaRecoveryCode]:
    rows = await db.execute(
        select(UserMfaRecoveryCode).where(UserMfaRecoveryCode.user_id == user_id, UserMfaRecoveryCode.used_at.is_(None))
    )
    return list(rows.scalars())


async def delete_recovery_codes(db: AsyncSession, user_id: uuid.UUID) -> None:
    from sqlalchemy import delete

    await db.execute(delete(UserMfaRecoveryCode).where(UserMfaRecoveryCode.user_id == user_id))


async def claim_code(db: AsyncSession, code_id: uuid.UUID) -> bool:
    """Atomically consume a code (False if someone else consumed it first)."""
    res = await db.execute(
        update(AuthOneTimeCode)
        .where(AuthOneTimeCode.id == code_id, AuthOneTimeCode.consumed_at.is_(None))
        .values(consumed_at=func.now())
        .returning(AuthOneTimeCode.id)
    )
    return res.first() is not None


async def claim_rotation(db: AsyncSession, session_id: uuid.UUID) -> bool:
    """Atomically mark a refresh token as rotated (False = already used: reuse)."""
    res = await db.execute(
        update(UserSession)
        .where(UserSession.id == session_id, UserSession.revoked_at.is_(None))
        .values(revoked_at=func.now(), revoke_reason="ROTATED", last_used_at=func.now())
        .returning(UserSession.id)
    )
    return res.first() is not None


async def set_replaced_by(db: AsyncSession, session_id: uuid.UUID, new_id: uuid.UUID) -> None:
    await db.execute(update(UserSession).where(UserSession.id == session_id).values(replaced_by_id=new_id))
