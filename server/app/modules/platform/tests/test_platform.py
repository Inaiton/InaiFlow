from datetime import date, timedelta

from app.core.config import get_settings
from tests import factories as f

API = f.API


async def test_meta(client):
    states = (await client.get(f"{API}/meta/states")).json()
    assert {"code": "33", "name": "Tamil Nadu"} in states
    keys = (await client.get(f"{API}/meta/permission-keys")).json()
    assert [m["module"] for m in keys] == ["accounts", "operations", "documents", "organization"]
    assert sum(len(m["keys"]) for m in keys) == 27


async def test_cron_requires_secret_and_runs(client, owner):
    assert (await client.get(f"{API}/internal/cron/daily")).status_code == 401
    assert (
        await client.get(f"{API}/internal/cron/daily", headers={"Authorization": "Bearer wrong"})
    ).status_code == 401
    expired = await f.add_member(owner.org_id, "OPERATOR")
    await f.sql(
        "UPDATE org_memberships SET access_expires_at = now() - interval '1 day' WHERE id=:m", m=expired.membership_id
    )
    await f.sql("INSERT INTO calibration_instruments (org_id, instrument_code, name, last_calibrated_date, next_due_date) "
                "VALUES (:o, 'VC-1', 'Vernier', :l, :d)", o=owner.org_id, l=date.today() - timedelta(days=400),
                d=date.today() - timedelta(days=1))  # fmt: skip
    r = await client.get(
        f"{API}/internal/cron/daily", headers={"Authorization": f"Bearer {get_settings().CRON_SECRET}"}
    )
    body = r.json()
    assert r.status_code == 200 and body["orgs_processed"] >= 1 and body["memberships_expired"] >= 1
    assert body["instruments_updated"] >= 1
    status = await f.sql("SELECT status FROM calibration_instruments WHERE org_id=:o", o=owner.org_id)
    assert status[0][0] == "EXPIRED"
    again = (
        await client.get(
            f"{API}/internal/cron/daily", headers={"Authorization": f"Bearer {get_settings().CRON_SECRET}"}
        )
    ).json()
    assert again["instruments_updated"] == 0  # idempotent


async def test_local_storage_tokens(client):
    from app.adapters.storage import get_storage

    storage = get_storage()
    t = await storage.create_upload_ticket("org/x/test.txt", "text/plain", 5)
    assert (await client.put(t.upload_url, content=b"toolarge!!", headers=t.headers)).status_code == 413
    assert (await client.put(t.upload_url, content=b"hello", headers=t.headers)).status_code == 204
    d = await storage.create_download_url("org/x/test.txt", filename="a b.txt")
    got = await client.get(d.url)
    assert got.content == b"hello" and 'filename="a_b.txt"' in got.headers["content-disposition"]
    assert (await client.get(t.upload_url)).status_code == 404  # put token cannot download
    assert (await client.put(f"{API}/storage/local/garbage", content=b"x")).status_code == 401


async def test_local_storage_404_when_provider_not_local(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "STORAGE_PROVIDER", "supabase")
    assert (await client.get(f"{API}/storage/local/anything")).status_code == 404


async def test_get_config_effective_dating(client):
    from app.core.db import get_sessionmaker
    from app.modules.platform.interface import get_config

    async with get_sessionmaker()() as s, s.begin():
        cfg_id = (
            await s.execute(
                __import__("sqlalchemy").text(
                    "SELECT id FROM platform_global_configs WHERE config_category='PAYROLL_STATUTORY' AND config_key='ESIC'"
                )
            )
        ).scalar()
        await s.execute(
            __import__("sqlalchemy").text(
                "INSERT INTO platform_global_config_versions (config_id, version, payload, effective_from) "
                "VALUES (:i, 99, '{\"gross_ceiling\": \"25000\"}'::jsonb, '2030-04-01')"
            ),
            {"i": cfg_id},
        )
        old = await get_config(s, "PAYROLL_STATUTORY", "ESIC", on_date=date(2026, 5, 1))
        new = await get_config(s, "PAYROLL_STATUTORY", "ESIC", on_date=date(2030, 5, 1))
        assert old["gross_ceiling"] == "21000" and new["gross_ceiling"] == "25000"
        await s.rollback()
