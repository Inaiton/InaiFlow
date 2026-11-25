"""DB-backed rate limiting (plan §3.2): >5 failed logins per email or >20 per IP in 15 min -> 429.

Attempts are recorded in an *independent* transaction so they survive the failing request.
"""

from __future__ import annotations

import ipaddress
from datetime import timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import independent_session
from app.core.errors import RateLimitedError

WINDOW = timedelta(minutes=15)
MAX_FAILURES_PER_EMAIL = 5
MAX_FAILURES_PER_IP = 20
MAX_CODES_PER_HOUR = 5


def _ip(ip: str | None) -> str | None:
    if not ip:
        return None
    try:
        return str(ipaddress.ip_address(ip))
    except ValueError:
        return None


async def check_login_allowed(db: AsyncSession, email: str, ip: str | None) -> None:
    row = (
        await db.execute(
            text(
                "SELECT count(*) FILTER (WHERE email = :email) AS by_email, "
                "count(*) FILTER (WHERE ip = CAST(:ip AS inet)) AS by_ip FROM auth_login_attempts "
                "WHERE NOT success AND created_at > now() - make_interval(secs => :secs) "
                "AND (email = :email OR ip = CAST(:ip AS inet))"
            ),
            {"email": email.lower(), "ip": _ip(ip), "secs": WINDOW.total_seconds()},
        )
    ).one()
    if row.by_email >= MAX_FAILURES_PER_EMAIL or (ip and row.by_ip >= MAX_FAILURES_PER_IP):
        raise RateLimitedError(headers={"Retry-After": str(int(WINDOW.total_seconds()))})


async def record_login_attempt(email: str | None, ip: str | None, success: bool) -> None:
    async with independent_session() as s:
        await s.execute(
            text("INSERT INTO auth_login_attempts (email, ip, success) VALUES (:email, CAST(:ip AS inet), :ok)"),
            {"email": email.lower() if email else None, "ip": _ip(ip), "ok": success},
        )


async def check_code_send_allowed(db: AsyncSession, email: str, purpose: str) -> bool:
    """False when too many codes were issued for this email+purpose in the last hour (silently skip)."""
    count = (
        await db.execute(
            text(
                "SELECT count(*) FROM auth_one_time_codes WHERE email = :email AND purpose = :purpose "
                "AND created_at > now() - interval '1 hour'"
            ),
            {"email": email.lower(), "purpose": purpose},
        )
    ).scalar_one()
    return int(count) < MAX_CODES_PER_HOUR
