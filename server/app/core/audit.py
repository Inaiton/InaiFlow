"""Immutable org audit trail (``org_audit_logs``; append-only, app role has SELECT+INSERT only).

    await write_audit(db, ctx, "ACCOUNTS", "UPDATE", "voucher", v.id, before=old, after=new, reason=...)

or decorate a service function ``async def create_x(db, ctx, ...) -> obj_with_id``::

    @audited(module="ACCOUNTS", action="CREATE", entity="voucher")
"""

from __future__ import annotations

import functools
import ipaddress
import json
import uuid
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, ParamSpec, TypeVar

from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import TenantContext
from app.core.money import to_str

MODULES = frozenset({"ACCOUNTS", "OPERATIONS", "DOCUMENTS", "ORGANIZATION", "PAYROLL", "TAXATION", "PLATFORM"})
ACTIONS = frozenset(
    {"CREATE", "UPDATE", "DELETE", "CANCEL", "APPROVE", "REJECT", "LOCK", "UNLOCK", "OVERRIDE", "EXPORT",
     "TRANSITION", "LOGIN", "INVITE", "ACCEPT", "REVOKE", "TRANSFER", "POST", "SIGNOFF", "EXECUTE"}
)  # fmt: skip


def to_jsonable(value: Any) -> Any:
    """Decimal -> str (wire format), UUID/date -> str, models/dataclasses -> dicts. Never floats."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return str(value)
    if isinstance(value, Decimal):
        return to_str(value)
    if isinstance(value, (uuid.UUID, ipaddress.IPv4Address, ipaddress.IPv6Address)):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, BaseModel):
        return to_jsonable(value.model_dump(mode="python"))
    if is_dataclass(value) and not isinstance(value, type):
        return to_jsonable(asdict(value))
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return to_jsonable(value.to_dict())
    if isinstance(value, Mapping):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [to_jsonable(v) for v in value]
    return str(value)


def diff(before: Mapping[str, Any] | None, after: Mapping[str, Any] | None) -> tuple[dict | None, dict | None]:
    """Reduce two snapshots to the changed keys only (field-level Before vs After)."""
    if before is None or after is None:
        return (to_jsonable(before), to_jsonable(after))
    b, a = to_jsonable(before), to_jsonable(after)
    keys = {k for k in set(b) | set(a) if b.get(k) != a.get(k)}
    return ({k: b.get(k) for k in keys}, {k: a.get(k) for k in keys})


def _ip(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return str(ipaddress.ip_address(value))
    except ValueError:
        return None


async def write_audit(
    db: AsyncSession,
    ctx: TenantContext,
    module: str,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID,
    before: Any = None,
    after: Any = None,
    reason: str | None = None,
    *,
    changed_only: bool = False,
) -> None:
    if changed_only and isinstance(before, Mapping) and isinstance(after, Mapping):
        before, after = diff(before, after)
    await db.execute(
        text(
            "INSERT INTO org_audit_logs (org_id, user_id, actor_type, actor_id, role_code, module, action, "
            "entity_type, entity_id, before_diff, after_diff, reason, ip_address) VALUES (:org, :uid, :atype, "
            ":aid, :role, :module, :action, :etype, :eid, CAST(:before AS jsonb), CAST(:after AS jsonb), "
            ":reason, CAST(:ip AS inet))"
        ),
        {
            "org": ctx.org_id,
            "uid": ctx.audit_user_id,
            "atype": ctx.actor_type,
            "aid": ctx.actor_id if ctx.actor_id is not None else ctx.user_id,
            "role": ctx.role_code,
            "module": module,
            "action": action,
            "etype": entity_type,
            "eid": entity_id,
            "before": None if before is None else json.dumps(to_jsonable(before)),
            "after": None if after is None else json.dumps(to_jsonable(after)),
            "reason": reason,
            "ip": _ip(ctx.ip),
        },
    )


P = ParamSpec("P")
R = TypeVar("R")


def _entity_id(result: Any) -> uuid.UUID | None:
    if isinstance(result, Mapping):
        value = result.get("id")
    else:
        value = getattr(result, "id", None)
    return value if isinstance(value, uuid.UUID) else (uuid.UUID(str(value)) if value else None)


def audited(
    *, module: str, action: str, entity: str
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    """Decorator for ``async def fn(db, ctx, ...)``: records an audit row with the result as ``after``."""

    def wrap(fn: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        @functools.wraps(fn)
        async def inner(*args: P.args, **kwargs: P.kwargs) -> R:
            result = await fn(*args, **kwargs)
            db = kwargs.get("db", args[0] if args else None)
            ctx = kwargs.get("ctx", args[1] if len(args) > 1 else None)
            eid = _entity_id(result)
            if isinstance(db, AsyncSession) and isinstance(ctx, TenantContext) and eid is not None:
                await write_audit(db, ctx, module, action, entity, eid, after=result)
            return result

        return inner

    return wrap
