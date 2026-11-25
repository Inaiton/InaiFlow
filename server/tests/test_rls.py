"""Row-Level Security suite: org A can never see or write org B rows under the app role."""

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.core.db import get_sessionmaker, set_tenant_scope
from tests import factories as f

API = f.API


async def _tenant_tables() -> list[str]:
    rows = await f.sql(
        "SELECT c.table_name FROM information_schema.columns c JOIN information_schema.tables t "
        "ON t.table_name = c.table_name AND t.table_schema = c.table_schema WHERE c.table_schema='public' "
        "AND c.column_name='org_id' AND t.table_type='BASE TABLE' ORDER BY 1"
    )
    return [r[0] for r in rows]


async def test_every_tenant_table_has_forced_rls_and_policy():
    tables = await _tenant_tables()
    assert len(tables) >= 40
    meta = {r[0]: (r[1], r[2]) for r in await f.sql(
        "SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class WHERE relnamespace='public'::regnamespace")}  # fmt: skip
    policies = {r[0]: (r[1], r[2], r[3]) for r in await f.sql(
        "SELECT tablename, roles::text, qual, with_check FROM pg_policies WHERE policyname LIKE 'tenant_isolation_%'")}  # fmt: skip
    for t in [*tables, "organizations"]:
        assert meta[t] == (True, True), f"{t} lacks ENABLE/FORCE RLS"
        roles, qual, check = policies[t]
        assert "inaiflow_app" in roles and "app.current_org_id" in qual and "app.current_org_id" in check, t


@pytest.fixture
async def two_orgs(client):
    a = await f.org_with_owner(client)
    b = await f.org_with_owner(client)
    return a, b


async def test_cross_tenant_reads_return_nothing(two_orgs):
    a, b = two_orgs
    tables = await _tenant_tables()
    async with get_sessionmaker()() as s, s.begin():
        await set_tenant_scope(s, a.org_id, a.user_id)
        for t in tables:
            if t in ("platform_impersonation_sessions",):
                continue
            n = (await s.execute(text(f"SELECT count(*) FROM {t} WHERE org_id = :b"), {"b": b.org_id})).scalar()  # noqa: S608
            assert n == 0, f"{t} leaks org B rows"
        assert (await s.execute(text("SELECT count(*) FROM organizations"))).scalar() == 1
        own = (await s.execute(text("SELECT count(*) FROM ledgers"))).scalar()
        assert own >= 28


async def test_missing_guc_returns_zero_rows(two_orgs):
    async with get_sessionmaker()() as s, s.begin():
        await s.execute(text("SET LOCAL ROLE inaiflow_app"))
        for t in ("ledgers", "account_groups", "org_memberships", "org_roles", "doc_folders", "organizations"):
            assert (await s.execute(text(f"SELECT count(*) FROM {t}"))).scalar() == 0, t  # noqa: S608


@pytest.mark.parametrize(
    ("table", "columns"),
    [
        ("ledgers", "(org_id, group_id, name) VALUES (:b, (SELECT id FROM account_groups LIMIT 1), 'Forged')"),
        ("org_branches", "(org_id, name) VALUES (:b, 'Forged')"),
        (
            "org_audit_logs",
            "(org_id, role_code, module, action, entity_type, entity_id) VALUES (:b,'X','ORGANIZATION','CREATE','x', gen_random_uuid())",
        ),
        (
            "resource_acl",
            "(org_id, subject_type, subject_id, resource_type, resource_id, access_level) VALUES (:b,'USER',gen_random_uuid(),'GODOWN',gen_random_uuid(),'FULL')",
        ),
        ("org_sequences", "(org_id, seq_key, next_value) VALUES (:b, 'X', 1)"),
    ],
)
async def test_cross_tenant_insert_blocked(two_orgs, table, columns):
    a, b = two_orgs
    async with get_sessionmaker()() as s:
        await s.begin()
        await set_tenant_scope(s, a.org_id, a.user_id)
        with pytest.raises(DBAPIError, match="row-level security"):
            await s.execute(text(f"INSERT INTO {table} {columns}"), {"b": b.org_id})  # noqa: S608
        await s.rollback()


async def test_cross_tenant_update_and_move_blocked(two_orgs):
    a, b = two_orgs
    async with get_sessionmaker()() as s:
        await s.begin()
        await set_tenant_scope(s, a.org_id, a.user_id)
        res = await s.execute(text("UPDATE ledgers SET name = name || '!' WHERE org_id = :b"), {"b": b.org_id})
        assert res.rowcount == 0
        res = await s.execute(text("DELETE FROM doc_folders WHERE org_id = :b"), {"b": b.org_id})
        assert res.rowcount == 0
        with pytest.raises(DBAPIError, match="row-level security"):
            await s.execute(text("UPDATE ledgers SET org_id = :b WHERE system_code = 'CASH'"), {"b": b.org_id})
        await s.rollback()


async def test_audit_log_append_only(two_orgs):
    a, _ = two_orgs
    async with get_sessionmaker()() as s:
        await s.begin()
        await set_tenant_scope(s, a.org_id, a.user_id)
        with pytest.raises(DBAPIError, match="permission denied"):
            await s.execute(text("UPDATE org_audit_logs SET reason = 'x'"))
        await s.rollback()
    async with get_sessionmaker()() as s:  # even the table owner is stopped by the trigger
        await s.begin()
        with pytest.raises(DBAPIError, match="append-only"):
            await s.execute(text("DELETE FROM org_audit_logs WHERE org_id = :a"), {"a": a.org_id})
        await s.rollback()


async def test_app_role_cannot_read_password_hashes(two_orgs):
    a, _ = two_orgs
    async with get_sessionmaker()() as s:
        await s.begin()
        await set_tenant_scope(s, a.org_id, a.user_id)
        assert (await s.execute(text("SELECT full_name FROM users WHERE id = :u"), {"u": a.user_id})).scalar()
        with pytest.raises(DBAPIError, match="permission denied"):
            await s.execute(text("SELECT password_hash FROM users LIMIT 1"))
        await s.rollback()


async def test_api_forged_ids_do_not_leak(client, two_orgs):
    a, b = two_orgs
    b_branch = (await client.post(f"{API}/organization/branches", json={"name": "B Plant"}, headers=b.headers)).json()
    r = await client.patch(f"{API}/organization/branches/{b_branch['id']}", json={"name": "hijack"}, headers=a.headers)
    assert r.status_code == 404
    b_role = await f.role_id(b.org_id, "ADMIN")
    r = await client.patch(f"{API}/organization/roles/{b_role}", json={"role_name": "x"}, headers=a.headers)
    assert r.status_code == 404
    r = await client.patch(
        f"{API}/organization/members/{b.membership_id}", json={"status": "SUSPENDED"}, headers=a.headers
    )
    assert r.status_code == 404
    assert uuid.UUID(b_branch["id"])
