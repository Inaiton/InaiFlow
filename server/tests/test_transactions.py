"""Commit-time failures surface as error responses; Idempotency-Key replays; sequences."""

from typing import Annotated

import httpx
import pytest
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text

from app.core.context import TenantContext
from app.core.deps import TenantDB, require
from app.core.idempotency import Idem
from app.core.sequences import format_number, next_value
from tests import factories as f

router = APIRouter()
Writer = Annotated[TenantContext, Depends(require("accounts.vouchers", "WRITE"))]


class Num(BaseModel):
    n: int
    number: str


async def _voucher(db, ctx, dr: str, cr: str):  # noqa: ANN001,ANN202
    vt = (await db.execute(text("SELECT id FROM voucher_types WHERE base_type='JOURNAL'"))).scalar()
    cash, sales = (
        (await db.execute(text("SELECT id FROM ledgers WHERE system_code IN ('CASH','SALES') ORDER BY system_code")))
        .scalars()
        .all()
    )
    vid = (await db.execute(text(
        "INSERT INTO vouchers (org_id, voucher_type_id, voucher_number, voucher_date, total_amount, created_by) "
        "VALUES (:o, :vt, :num, current_date, :amt, :u) RETURNING id"),
        {"o": ctx.org_id, "vt": vt, "num": f.unique("JV"), "amt": dr, "u": ctx.user_id})).scalar()  # fmt: skip
    for ledger, typ, amt in ((cash, "DR", dr), (sales, "CR", cr)):
        await db.execute(text("INSERT INTO voucher_entries (org_id, voucher_id, ledger_id, entry_type, amount) "
                              "VALUES (:o, :v, :l, :t, CAST(:a AS numeric))"),
                         {"o": ctx.org_id, "v": vid, "l": ledger, "t": typ, "a": amt})  # fmt: skip
    return vid


@router.post("/test/unbalanced", status_code=201)
async def unbalanced(ctx: Writer, db: TenantDB) -> dict:
    await _voucher(db, ctx, "100.00", "90.00")  # the deferred trigger fires at COMMIT
    return {"ok": True}


@router.post("/test/balanced", status_code=201)
async def balanced(ctx: Writer, db: TenantDB) -> dict:
    return {"id": str(await _voucher(db, ctx, "100.00", "100.00"))}


@router.post("/test/numbered", status_code=201, response_model=Num)
async def numbered(body: dict, ctx: Writer, db: TenantDB, idem: Idem) -> Num:
    n = await next_value(db, ctx.org_id, "TEST")
    return await idem.save(Num(n=n, number=format_number("T-", n, 3)), 201)


@pytest.fixture(scope="module")
def test_app():
    from app.main import create_app

    app = create_app()
    app.include_router(router, prefix="/api/v1")
    return app


@pytest.fixture
async def tclient(test_app):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=test_app), base_url="http://t") as c:
        yield c


async def test_commit_time_trigger_failure_is_an_error_response(tclient, owner):
    before = (await f.sql("SELECT count(*) FROM vouchers WHERE org_id=:o", o=owner.org_id))[0][0]
    r = await tclient.post("/api/v1/test/unbalanced", headers=owner.headers)
    assert r.status_code == 400 and r.json()["error"]["code"] == "DOUBLE_ENTRY_IMBALANCE"
    assert (await f.sql("SELECT count(*) FROM vouchers WHERE org_id=:o", o=owner.org_id))[0][0] == before
    ok = await tclient.post("/api/v1/test/balanced", headers=owner.headers)
    assert ok.status_code == 201
    assert (await f.sql("SELECT count(*) FROM vouchers WHERE org_id=:o", o=owner.org_id))[0][0] == before + 1


async def test_permission_checked_before_work(tclient, owner):
    op = await f.add_member(owner.org_id, "OPERATOR")
    assert (await tclient.post("/api/v1/test/balanced", headers=op.headers)).status_code == 403


async def test_idempotency_replay_and_conflict(tclient, owner):
    h = {**owner.headers, "Idempotency-Key": f.unique("k")}
    r1 = await tclient.post("/api/v1/test/numbered", json={"a": 1}, headers=h)
    r2 = await tclient.post("/api/v1/test/numbered", json={"a": 1}, headers=h)
    assert r1.status_code == r2.status_code == 201 and r1.json() == r2.json()
    assert r2.headers.get("idempotent-replayed") == "true"
    r3 = await tclient.post("/api/v1/test/numbered", json={"a": 2}, headers=h)
    assert r3.status_code == 409 and r3.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"
    r4 = await tclient.post("/api/v1/test/numbered", json={"a": 1}, headers=owner.headers)
    assert r4.json()["n"] == r1.json()["n"] + 1 and r4.json()["number"] == f"T-{r4.json()['n']:03d}"


async def test_failed_request_leaves_no_idempotency_row(tclient, owner):
    key = f.unique("k")
    await tclient.post("/api/v1/test/unbalanced", headers={**owner.headers, "Idempotency-Key": key})
    assert await f.sql("SELECT 1 FROM idempotency_keys WHERE key=:k", k=key) == []


async def test_error_shapes(tclient, owner):
    r = await tclient.post(
        "/api/v1/test/numbered", content=b"not json", headers={**owner.headers, "Content-Type": "application/json"}
    )
    assert r.status_code == 422 and r.json()["error"]["code"] == "VALIDATION_ERROR"
    r = await tclient.get("/api/v1/nope")
    assert r.status_code == 404 and r.json()["error"]["code"] == "NOT_FOUND"
    assert r.headers["x-content-type-options"] == "nosniff" and r.headers["cache-control"] == "no-store"
