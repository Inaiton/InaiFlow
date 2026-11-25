"""Test helpers (copy of accounts/tests/helpers.py; import-linter forbids importing accounts internals) (org FY 2026-27, state 33 Tamil Nadu)."""

from __future__ import annotations

from typing import Any

from tests.factories import unique

A = "/api/v1/accounts"


async def groups(client, actor) -> dict[str, str]:  # noqa: ANN001
    r = await client.get(f"{A}/groups", headers=actor.headers)
    assert r.status_code == 200, r.text
    return {g["system_code"]: g["id"] for g in r.json() if g["system_code"]}


async def ledgers(client, actor) -> dict[str, str]:  # noqa: ANN001
    r = await client.get(f"{A}/ledgers", params={"limit": 200}, headers=actor.headers)
    assert r.status_code == 200, r.text
    return {lg["system_code"]: lg["id"] for lg in r.json()["items"] if lg["system_code"]}


async def vtypes(client, actor) -> dict[str, str]:  # noqa: ANN001
    r = await client.get(f"{A}/voucher-types", headers=actor.headers)
    return {v["base_type"]: v["id"] for v in r.json() if v["is_system"]}


async def ledger(client, actor, group_code: str, name: str | None = None, **extra: Any) -> str:  # noqa: ANN001
    g = await groups(client, actor)
    body = {"group_id": g[group_code], "name": name or unique("L-"), **extra}
    r = await client.post(f"{A}/ledgers", json=body, headers=actor.headers)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def e(ledger_id: str, side: str, amount: str, **kw: Any) -> dict[str, Any]:
    return {"ledger_id": ledger_id, "entry_type": side, "amount": amount, **kw}


async def voucher(client, actor, base_type: str, day: str, entries: list, expect: int = 201, **kw: Any):  # noqa: ANN001,ANN201
    vt = await vtypes(client, actor)
    body = {"voucher_type_id": vt[base_type], "voucher_date": day, "entries": entries, **kw}
    r = await client.post(f"{A}/vouchers", json=body, headers=actor.headers)
    assert r.status_code == expect, r.text
    return r.json()
