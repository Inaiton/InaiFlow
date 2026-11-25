"""Configs (validation, versioning, effective dates, push), plans, invoices, admin accounts, audit log."""

import uuid
from datetime import date, timedelta

import pytest

from app.core.db import get_sessionmaker
from app.modules.platform.interface import get_config
from app.modules.superadmin.config_schemas import validate_payload
from app.seeds import config_rows
from tests import factories as f

from . import helpers as h

API = h.API


@pytest.mark.parametrize("row", config_rows(), ids=lambda r: f"{r['category']}/{r['key']}")
def test_seed_payloads_validate(row):
    validate_payload(row["category"], row["key"], row["payload"])


def test_invalid_payloads_rejected():
    from app.core.errors import ValidationFailedError

    gst = next(r["payload"] for r in config_rows() if r["category"] == "GST_SLABS")
    with pytest.raises(ValidationFailedError):
        validate_payload("GST_SLABS", "default", {**gst, "rates": [18.0]})  # floats are not money
    with pytest.raises(ValidationFailedError):
        validate_payload("PAYROLL_STATUTORY", "EPF", {"wage_ceiling": "15000"})
    with pytest.raises(ValidationFailedError):
        validate_payload("FOLDER_TEMPLATES", "MONTHLY", {"subfolders": [{"name": "Bills", "system_kind": "BILLS"}]})
    with pytest.raises(ValidationFailedError):
        validate_payload("DEFAULT_ROLES", "ADMIN", {"role_code": "ADMIN", "role_name": "Admin",
                                                    "permissions": {"accounts.nope": "FULL"}})  # fmt: skip
    assert validate_payload("CUSTOM_THING", "x", {"anything": [1, 2]}) == {"anything": [1, 2]}


async def test_config_versioning_and_effective_dates(client):
    admin = await h.admin_with_token(client)
    key = f.unique("k")
    epf = next(r["payload"] for r in config_rows() if r["key"] == "EPF")
    r = await client.post(f"{API}/admin/configs", json={"config_category": "EPF_TEST", "config_key": key,
                          "display_name": "EPF test", "payload": {"x": 1}, "reason": "initial", "effective_from": "2025-04-01"},
                          headers=admin.headers)  # fmt: skip
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    assert r.json()["version"] == 1 and r.json()["effective_from"] == "2025-04-01"
    dup = await client.post(f"{API}/admin/configs", json={"config_category": "EPF_TEST", "config_key": key,
                            "display_name": "dup", "payload": {}, "reason": "dup again"}, headers=admin.headers)  # fmt: skip
    assert dup.status_code == 409
    future = date.today() + timedelta(days=30)
    r = await client.put(f"{API}/admin/configs/{cid}", json={"payload": {"x": 2}, "effective_from": str(future),
                         "reason": "budget change"}, headers=admin.headers)  # fmt: skip
    assert r.status_code == 200 and r.json()["version"] == 2 and r.json()["updated_by_name"] == "Test Admin"
    hist = (await client.get(f"{API}/admin/configs/{cid}/history", headers=admin.headers)).json()
    assert [v["version"] for v in hist] == [2, 1] and hist[0]["change_reason"] == "budget change"
    async with get_sessionmaker()() as s:
        assert await get_config(s, "EPF_TEST", key, on_date=date.today()) == {"x": 1}
        assert await get_config(s, "EPF_TEST", key, on_date=future) == {"x": 2}
    listed = (await client.get(f"{API}/admin/configs", params={"category": "EPF_TEST"}, headers=admin.headers)).json()
    assert any(c["id"] == cid for c in listed)
    # statutory configs are validated against their seed shape
    sys_cfg = next(c for c in (await client.get(f"{API}/admin/configs", params={"category": "PAYROLL_STATUTORY"},
                                                headers=admin.headers)).json() if c["config_key"] == "EPF")  # fmt: skip
    bad = await client.put(f"{API}/admin/configs/{sys_cfg['id']}", json={"payload": {**epf, "employee_rate": 12.0},
                           "reason": "typo test"}, headers=admin.headers)  # fmt: skip
    assert bad.status_code in (400, 422)
    assert "CONFIG_UPDATE" in await h.audit_actions(uuid.UUID(cid))


async def test_config_roles(client):
    support = await h.admin_with_token(client, "SUPPORT_ADMIN")
    cfgs = (await client.get(f"{API}/admin/configs", headers=support.headers)).json()
    assert (
        cfgs and (await client.get(f"{API}/admin/configs/{cfgs[0]['id']}", headers=support.headers)).status_code == 200
    )
    r = await client.put(f"{API}/admin/configs/{cfgs[0]['id']}", json={"payload": cfgs[0]["payload"], "reason": "nope"},
                         headers=support.headers)  # fmt: skip
    assert r.status_code == 403


async def test_push(client, owner):
    admin = await h.admin_with_token(client)
    cfgs = (await client.get(f"{API}/admin/configs", headers=admin.headers)).json()
    gst = next(c for c in cfgs if c["config_category"] == "GST_SLABS")
    r = await client.post(f"{API}/admin/configs/{gst['id']}/push", json={"all_orgs": True, "reason": "try push"},
                          headers=admin.headers)  # fmt: skip
    assert r.status_code == 409
    role = next(c for c in cfgs if c["config_category"] == "DEFAULT_ROLES" and c["config_key"] == "ACCOUNTANT")
    url = f"{API}/admin/configs/{role['id']}/push"
    assert (await client.post(url, json={"reason": "no targets"}, headers=admin.headers)).status_code == 400
    r = await client.post(url, json={"org_ids": [str(owner.org_id)], "reason": "matrix refresh"}, headers=admin.headers)
    assert r.status_code == 200
    body = r.json()
    assert body == {"orgs_updated": 1, "orgs_skipped": 0}
    assert "CONFIG_PUSH" in await h.audit_actions(uuid.UUID(role["id"]))


async def test_plans_and_invoices(client, owner):
    admin = await h.admin_with_token(client, "BILLING_ADMIN")
    code = f.unique("P").upper()
    body = {"plan_code": code, "name": "Growth", "monthly_price_inr": "2999.00", "annual_price_inr": "29990",
            "max_internal_seats": 25, "max_external_collaborators": 5, "max_storage_gb": 50,
            "enabled_modules": {"accounts": True, "payroll": True}, "reason": "new tier"}  # fmt: skip
    r = await client.post(f"{API}/admin/plans", json=body, headers=admin.headers)
    assert r.status_code == 201, r.text
    plan = r.json()
    assert plan["monthly_price_inr"] == "2999.00" and plan["org_count"] == 0 and plan["is_active"] is True
    assert (await client.post(f"{API}/admin/plans", json=body, headers=admin.headers)).status_code == 409
    bad = await client.post(f"{API}/admin/plans", json={**body, "plan_code": code + "X", "enabled_modules": {"x": True}},
                            headers=admin.headers)  # fmt: skip
    assert bad.status_code == 400
    assert (await client.post(f"{API}/admin/plans", json={**body, "monthly_price_inr": 1.5},
                              headers=admin.headers)).status_code == 422  # fmt: skip
    r = await client.patch(f"{API}/admin/plans/{plan['id']}", json={"name": "Growth+", "reason": "rename"},
                           headers=admin.headers)  # fmt: skip
    assert r.json()["name"] == "Growth+" and r.json()["max_storage_gb"] == 50

    inv_body = {"org_id": str(owner.org_id), "period_start": "2026-11-01", "period_end": "2026-11-30",
                "amount_inr": "2999.00", "reason": "november"}  # fmt: skip
    r1 = await client.post(f"{API}/admin/billing/invoices", json=inv_body, headers=admin.headers)
    r2 = await client.post(f"{API}/admin/billing/invoices", json=inv_body, headers=admin.headers)
    assert r1.status_code == r2.status_code == 201, r1.text
    n1, n2 = r1.json()["invoice_number"], r2.json()["invoice_number"]
    assert n1.startswith(f"INV-{date.today():%Y%m}-") and len(n1) == len("INV-202611-0001")
    assert int(n2[-4:]) == int(n1[-4:]) + 1 and r1.json()["status"] == "DUE"
    url = f"{API}/admin/billing/invoices/{r1.json()['id']}"
    paid = await client.patch(url, json={"status": "PAID", "reason": "NEFT received"}, headers=admin.headers)
    assert paid.json()["status"] == "PAID" and paid.json()["paid_at"]
    assert (await client.patch(url, json={"status": "DUE", "reason": "undo"}, headers=admin.headers)).status_code == 409
    v = await client.patch(f"{API}/admin/billing/invoices/{r2.json()['id']}", json={"status": "VOID", "reason": "dup"},
                           headers=admin.headers)  # fmt: skip
    assert v.json()["status"] == "VOID"
    lst = await client.get(f"{API}/admin/billing/invoices", params={"org_id": str(owner.org_id), "status": "PAID"},
                           headers=admin.headers)  # fmt: skip
    assert lst.json()["total"] == 1 and lst.json()["items"][0]["org_name"]
    bad = {**inv_body, "period_end": "2026-10-01"}
    assert (await client.post(f"{API}/admin/billing/invoices", json=bad, headers=admin.headers)).status_code == 400


async def test_admin_accounts(client):
    sup = await h.admin_with_token(client)
    email = f"{f.unique('new')}@example.com"
    r = await client.post(f"{API}/admin/admins", json={"email": email, "full_name": "New Support", "role": "SUPPORT_ADMIN"},
                          headers=sup.headers)  # fmt: skip
    assert r.status_code == 201, r.text
    created = r.json()
    assert created["admin"]["mfa_enabled"] is False and len(created["temporary_password"]) >= 16
    dup = await client.post(f"{API}/admin/admins", json={"email": email, "full_name": "x", "role": "SUPPORT_ADMIN"},
                            headers=sup.headers)  # fmt: skip
    assert dup.status_code == 409
    login = await client.post(
        f"{API}/admin/auth/login", json={"email": email, "password": created["temporary_password"]}
    )
    assert login.json()["status"] == "PASSWORD_CHANGE_REQUIRED"
    # can't demote or deactivate yourself
    me = f"{API}/admin/admins/{sup.id}"
    assert (
        await client.patch(me, json={"role": "BILLING_ADMIN", "reason": "oops"}, headers=sup.headers)
    ).status_code == 409
    assert (await client.patch(me, json={"is_active": False, "reason": "oops"}, headers=sup.headers)).status_code == 409
    # deactivate another admin -> their sessions end
    other = await h.admin_with_token(client, "BILLING_ADMIN")
    r = await client.patch(f"{API}/admin/admins/{other.id}", json={"is_active": False, "reason": "left company"},
                           headers=sup.headers)  # fmt: skip
    assert r.status_code == 200 and r.json()["is_active"] is False
    assert (await client.get(f"{API}/admin/me", headers=other.headers)).status_code == 401
    lst = (await client.get(f"{API}/admin/admins", headers=sup.headers)).json()
    assert any(a["email"] == email for a in lst)
    assert await h.audit_actions(other.id) == ["ADMIN_LOGIN", "ADMIN_UPDATE"]


async def test_last_superadmin_rule(client, monkeypatch):
    from app.modules.superadmin import repository

    sup = await h.admin_with_token(client)
    other = await h.make_admin("SUPERADMIN")

    async def only_one(db):  # noqa: ANN001, ANN202 - shared test DB has many superadmins
        return 1

    monkeypatch.setattr(repository, "count_active_superadmins", only_one)
    r = await client.patch(f"{API}/admin/admins/{other.id}", json={"role": "SUPPORT_ADMIN", "reason": "demote"},
                           headers=sup.headers)  # fmt: skip
    assert r.status_code == 409


async def test_audit_log_filters(client):
    sup = await h.admin_with_token(client)
    r = await client.get(f"{API}/admin/audit-logs", params={"admin_id": str(sup.id), "action": "ADMIN_LOGIN",
                         "date_from": str(date.today()), "date_to": str(date.today())}, headers=sup.headers)  # fmt: skip
    assert r.status_code == 200 and r.json()["total"] == 1
    item = r.json()["items"][0]
    assert item["admin_email"] == sup.email and item["target_type"] == "PLATFORM_ADMIN"
