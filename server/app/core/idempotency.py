"""``Idempotency-Key`` support for mutating tenant endpoints (stored 24h per org+user+key).

    @router.post("/accounts/vouchers", status_code=201, response_model=VoucherOut)
    async def create(body: VoucherIn, ctx: Ctx, db: TenantDB, idem: Idem) -> VoucherOut:
        out = await service.create_voucher(db, ctx, body)
        return await idem.save(out, 201)

* same key + same request  -> stored response replayed (header ``Idempotent-Replayed: true``)
* same key + other request -> 409 ``IDEMPOTENCY_CONFLICT``
* same key still in flight -> the second request waits on the row lock, then replays
The placeholder row lives in the request transaction, so a failed request leaves no trace.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from typing import Annotated, Any, TypeVar

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import to_jsonable
from app.core.deps import TenantBase, TenantDB
from app.core.errors import ConflictError, IdempotencyConflictError, ValidationFailedError

HEADER = "Idempotency-Key"
TTL_HOURS = 24
T = TypeVar("T")


class IdempotentReplay(Exception):  # noqa: N818 - control-flow signal, not an error
    def __init__(self, status: int, body: Any) -> None:
        self.status, self.body = status, body


@dataclass
class Idempotency:
    key: str | None
    db: AsyncSession | None = None
    org_id: uuid.UUID | None = None
    user_id: uuid.UUID | None = None

    async def save(self, payload: T, status_code: int = 200) -> T:
        if self.key is None or self.db is None:
            return payload
        if isinstance(payload, BaseModel):
            body = payload.model_dump(mode="json")
        elif isinstance(payload, list):
            body = [p.model_dump(mode="json") if isinstance(p, BaseModel) else to_jsonable(p) for p in payload]
        else:
            body = to_jsonable(payload)
        await self.db.execute(
            text(
                "UPDATE idempotency_keys SET response_status = :st, response_body = CAST(:body AS jsonb) "
                "WHERE org_id = :org AND user_id = :uid AND key = :key"
            ),
            {"st": status_code, "body": json.dumps(body), "org": self.org_id, "uid": self.user_id, "key": self.key},
        )
        return payload


async def idempotency(request: Request, ctx: TenantBase, db: TenantDB) -> Idempotency:
    key = request.headers.get(HEADER)
    if not key or request.method not in ("POST", "PUT", "PATCH") or ctx.user_id is None:
        return Idempotency(None)
    key = key.strip()
    if not 1 <= len(key) <= 255:
        raise ValidationFailedError(f"{HEADER} must be 1-255 characters")
    digest = hashlib.sha256(
        request.method.encode() + b" " + request.url.path.encode() + b"\n" + await request.body()
    ).hexdigest()
    params = {"org": ctx.org_id, "uid": ctx.user_id, "key": key}
    await db.execute(
        text(
            "DELETE FROM idempotency_keys WHERE org_id = :org AND user_id = :uid AND key = :key "
            f"AND created_at < now() - interval '{TTL_HOURS} hours'"
        ),
        params,
    )
    inserted = (
        await db.execute(
            text(
                "INSERT INTO idempotency_keys (org_id, user_id, key, request_hash) VALUES (:org, :uid, :key, :h) "
                "ON CONFLICT (org_id, user_id, key) DO NOTHING RETURNING key"
            ),
            {**params, "h": digest},
        )
    ).first()
    if inserted is not None:
        return Idempotency(key, db, ctx.org_id, ctx.user_id)
    row = (
        await db.execute(
            text(
                "SELECT request_hash, response_status, response_body FROM idempotency_keys "
                "WHERE org_id = :org AND user_id = :uid AND key = :key FOR UPDATE"
            ),
            params,
        )
    ).first()
    if row is None or row.request_hash != digest:
        raise IdempotencyConflictError()
    if row.response_status is None:
        raise ConflictError("A request with this Idempotency-Key is still being processed")
    raise IdempotentReplay(row.response_status, row.response_body)


Idem = Annotated[Idempotency, Depends(idempotency, scope="function")]


def install_idempotency_handler(app: FastAPI) -> None:
    @app.exception_handler(IdempotentReplay)
    async def _replay(_: Request, exc: IdempotentReplay) -> JSONResponse:
        return JSONResponse(status_code=exc.status, content=exc.body, headers={"Idempotent-Replayed": "true"})
