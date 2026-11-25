"""Organizations & users: role enforcement, lifecycle effects on the tenant pipeline, impersonation, plan,
owner transfer, user actions, dashboard/meta/health, audit rows."""

import uuid

from tests import factories as f

from . import helpers as h

API = h.API


async def test_role_enforcement(client, owner):
    billing = await h.admin_with_token(client, "BILLING_ADMIN")
    support = await h.admin_with_token(client, "SUPPORT_ADMIN")
    org = owner.org_id
    imp = {"mode": "READ_ONLY", "ticket_reference": "T-1", "reason": "customer asked"}
    r = await client.post(f"{API}/admin/organizations/{org}/impersonate", json=imp, headers=billing.headers)
    assert r.status_code == 403
    r = await client.get(f"{API}/admin/users", headers=billing.headers)
    assert r.status_code == 403
    r = await client.post(f"{API}/admin/organizations/{org}/lifecycle",
                          json={"action": "ARCHIVE", "reason": "closing down"}, headers=support.headers)  # fmt: skip
    assert r.status_code == 403
    assert (await f.sql("SELECT org_status FROM organizations WHERE id=:o", o=org))[0][0] == "TRIAL"
    r = await client.get(f"{API}/admin/organizations/{org}", headers=billing.headers)
    assert r.status_code == 200 and r.json()["owner_email"] == owner.email
    plans = (await client.get(f"{API}/admin/plans", headers=support.headers)).json()
    r = await client.patch(f"{API}/admin/organizations/{org}/plan",
                           json={"plan_id": plans[0]["id"], "reason": "upgrade"}, headers=support.headers)  # fmt: skip
    assert r.status_code == 403
    for path in ("/admin/admins", "/admin/billing/invoices"):
        assert (await client.get(f"{API}{path}", headers=support.headers)).status_code == 403


async def test_lifecycle_effects_on_tenant_requests(client, owner):
    admin = await h.admin_with_token(client, "SUPPORT_ADMIN")
    org = owner.org_id
    url = f"{API}/admin/organizations/{org}/lifecycle"
    r = await client.post(url, json={"action": "SUSPEND", "reason": "non-payment"}, headers=admin.headers)
    assert r.status_code == 200 and r.json()["org_status"] == "SUSPENDED"
    t = await client.get(f"{API}/organization/profile", headers=owner.headers)
    assert t.status_code == 403 and t.json()["error"]["code"] == "ORG_SUSPENDED"
    r = await client.post(url, json={"action": "SUSPEND", "reason": "again"}, headers=admin.headers)
    assert r.status_code == 409
    r = await client.post(url, json={"action": "EXTEND_TRIAL", "reason": "more time"}, headers=admin.headers)
    assert r.status_code == 400  # trial_days required
    r = await client.post(url, json={"action": "EXTEND_TRIAL", "reason": "more time", "trial_days": 10},
                          headers=admin.headers)  # fmt: skip
    assert r.status_code == 200 and r.json()["org_status"] == "TRIAL" and r.json()["trial_ends_at"]
    assert (await client.get(f"{API}/organization/profile", headers=owner.headers)).status_code == 200
    r = await client.post(url, json={"action": "ACTIVATE", "reason": "paid"}, headers=admin.headers)
    assert r.json()["org_status"] == "ACTIVE"
    actions = await h.audit_actions(org)
    assert actions[:3] == ["ORG_SUSPEND", "ORG_EXTEND_TRIAL", "ORG_ACTIVATE"]
    row = (await f.sql("SELECT before_state, after_state, host(ip_address) FROM platform_audit_logs "
                       "WHERE target_id=:o AND action='ORG_SUSPEND'", o=org))[0]  # fmt: skip
    assert row[0]["org_status"] == "TRIAL" and row[1]["org_status"] == "SUSPENDED"
    assert row[1]["reason"] == "non-payment" and row[2]
    sup = await h.admin_with_token(client)
    r = await client.post(url, json={"action": "ARCHIVE", "reason": "closed"}, headers=sup.headers)
    assert r.status_code == 200 and r.json()["org_status"] == "ARCHIVED"
    assert (await client.get(f"{API}/organization/profile", headers=owner.headers)).status_code == 403


async def test_impersonation_read_only(client, owner):
    admin = await h.admin_with_token(client, "SUPPORT_ADMIN")
    r = await client.post(f"{API}/admin/organizations/{owner.org_id}/impersonate",
                          json={"mode": "READ_ONLY", "ticket_reference": "SUP-42", "reason": "investigate"},
                          headers=admin.headers)  # fmt: skip
    assert r.status_code == 201, r.text
    out = r.json()
    assert out["launch_url"].startswith("http://localhost:3000/impersonate#token=")
    assert out["launch_url"].endswith(f"&org_id={owner.org_id}") and "?" not in out["launch_url"]
    hdr = {"Authorization": f"Bearer {out['token']}", "X-Organization-ID": str(owner.org_id)}
    assert (await client.get(f"{API}/organization/profile", headers=hdr)).status_code == 200
    r = await client.post(f"{API}/organization/branches", json={"name": "Unit 2"}, headers=hdr)
    assert r.status_code == 403
    row = (await f.sql("SELECT mode, ticket_reference, expires_at - created_at FROM platform_impersonation_sessions "
                       "WHERE id=:i", i=uuid.UUID(out["session_id"])))[0]  # fmt: skip
    assert row[0] == "READ_ONLY" and row[1] == "SUP-42" and 29 * 60 <= row[2].total_seconds() <= 30 * 60 + 5
    assert "IMPERSONATION_START" in await h.audit_actions(owner.org_id)
    # suspending the org ends the support session
    sup = await h.admin_with_token(client)
    await client.post(f"{API}/admin/organizations/{owner.org_id}/lifecycle",
                      json={"action": "SUSPEND", "reason": "fraud"}, headers=sup.headers)  # fmt: skip
    assert (await client.get(f"{API}/organization/profile", headers=hdr)).status_code == 401


async def test_impersonation_full_support_writes_are_audited(client, owner):
    admin = await h.admin_with_token(client)
    out = (await client.post(f"{API}/admin/organizations/{owner.org_id}/impersonate",
                             json={"mode": "FULL_SUPPORT", "ticket_reference": "SUP-7", "reason": "fix data"},
                             headers=admin.headers)).json()  # fmt: skip
    hdr = {"Authorization": f"Bearer {out['token']}", "X-Organization-ID": str(owner.org_id)}
    r = await client.post(f"{API}/organization/branches", json={"name": f.unique("Unit ")}, headers=hdr)
    assert r.status_code == 201, r.text
    assert "IMPERSONATED_REQUEST" in await h.audit_actions(owner.org_id)


async def test_plan_change_and_quota_overrides(client, owner):
    admin = await h.admin_with_token(client, "BILLING_ADMIN")
    plans = {p["plan_code"]: p for p in (await client.get(f"{API}/admin/plans", headers=admin.headers)).json()}
    target = next(p for code, p in plans.items() if code != "FREE_TRIAL")
    url = f"{API}/admin/organizations/{owner.org_id}/plan"
    r = await client.patch(url, json={"plan_id": target["id"], "reason": "upgrade", "quota_overrides": {"bogus": 1}},
                           headers=admin.headers)  # fmt: skip
    assert r.status_code == 400
    q = {"max_internal_seats": 40, "enabled_modules": {"irp_einvoice": True}}
    r = await client.patch(url, json={"plan_id": target["id"], "reason": "upgrade", "quota_overrides": q},
                           headers=admin.headers)  # fmt: skip
    assert r.status_code == 200 and r.json()["plan_code"] == target["plan_code"]
    assert r.json()["quota_overrides"] == q
    bill = await client.get(f"{API}/organization/billing", headers=owner.headers)
    if bill.status_code == 200:
        assert bill.json()["plan_code"] == target["plan_code"]
    assert "ORG_PLAN_CHANGE" in await h.audit_actions(owner.org_id)


async def test_transfer_owner(client, owner):
    admin = await h.admin_with_token(client)
    url = f"{API}/admin/organizations/{owner.org_id}/transfer-owner"
    stranger = await f.create_user()
    r = await client.post(url, json={"new_owner_user_id": str(stranger.user_id), "reason": "request"},
                          headers=admin.headers)  # fmt: skip
    assert r.status_code == 400
    acct = await f.add_member(owner.org_id, "ACCOUNTANT")
    r = await client.post(url, json={"new_owner_user_id": str(acct.user_id), "reason": "founder left"},
                          headers=admin.headers)  # fmt: skip
    assert r.status_code == 200 and r.json()["owner_user_id"] == str(acct.user_id)
    members = (await client.get(f"{API}/admin/organizations/{owner.org_id}/members", headers=admin.headers)).json()
    roles = {m["user_id"]: m["role_code"] for m in members}
    assert roles[str(acct.user_id)] == "ORG_OWNER" and roles[str(owner.user_id)] == "ADMIN"


async def test_directory_filters_and_detail(client, owner):
    admin = await h.admin_with_token(client, "BILLING_ADMIN")
    slug = owner.extra["org"]["workspace_slug"]
    r = await client.get(f"{API}/admin/organizations", params={"q": slug, "status": "TRIAL"}, headers=admin.headers)
    assert r.status_code == 200 and r.json()["total"] == 1
    item = r.json()["items"][0]
    assert item["member_count"] == 1 and item["plan_code"] == "FREE_TRIAL"
    r = await client.get(f"{API}/admin/organizations", params={"q": slug, "status": "ACTIVE"}, headers=admin.headers)
    assert r.json()["total"] == 0
    d = (await client.get(f"{API}/admin/organizations/{owner.org_id}", headers=admin.headers)).json()
    assert d["voucher_count"] == 0 and d["storage_used_bytes"] == 0 and d["owner_name"] == "Olivia Owner"
    assert (await client.get(f"{API}/admin/organizations/{uuid.uuid4()}", headers=admin.headers)).status_code == 404


async def test_user_actions(client, owner):
    admin = await h.admin_with_token(client, "SUPPORT_ADMIN")
    url = f"{API}/admin/users/{owner.user_id}"
    d = (await client.get(url, headers=admin.headers)).json()
    assert d["memberships"][0]["role_code"] == "ORG_OWNER" and d["active_sessions"] >= 1 and d["org_count"] == 1

    async def act(action: str) -> dict:
        r = await client.post(f"{url}/actions", json={"action": action, "reason": "support ticket"},
                              headers=admin.headers)  # fmt: skip
        assert r.status_code == 200, r.text
        return r.json()

    assert (await act("SUSPEND"))["is_suspended"] is True
    r = await client.get(f"{API}/organization/profile", headers=owner.headers)
    assert r.status_code == 401  # sessions revoked on suspension
    assert (await act("UNSUSPEND"))["is_suspended"] is False
    again = await client.post(f"{url}/actions", json={"action": "UNSUSPEND", "reason": "x" * 5}, headers=admin.headers)
    assert again.status_code == 409

    mfa_user = await f.create_user(mfa=True, verified=False)
    murl = f"{API}/admin/users/{mfa_user.user_id}/actions"
    r = await client.post(murl, json={"action": "RESET_MFA", "reason": "lost phone"}, headers=admin.headers)
    assert r.json()["mfa_enabled"] is False
    assert (await f.sql("SELECT mfa_secret FROM users WHERE id=:u", u=mfa_user.user_id))[0][0] is None
    r = await client.post(murl, json={"action": "VERIFY_EMAIL", "reason": "verified by phone"}, headers=admin.headers)
    assert r.json()["is_email_verified"] is True
    assert (await client.get(f"{API}/me", headers=mfa_user.user_headers)).status_code == 200
    r = await client.post(murl, json={"action": "REVOKE_SESSIONS", "reason": "device stolen"}, headers=admin.headers)
    assert r.json()["active_sessions"] == 0
    assert (await client.get(f"{API}/me", headers=mfa_user.user_headers)).status_code == 401
    assert await h.audit_actions(mfa_user.user_id) == ["USER_RESET_MFA", "USER_VERIFY_EMAIL", "USER_REVOKE_SESSIONS"]
    r = await client.get(f"{API}/admin/users", params={"q": mfa_user.email}, headers=admin.headers)
    assert r.json()["total"] == 1 and r.json()["items"][0]["mfa_enabled"] is False


async def test_dashboard_health_tokens(client, owner):
    admin = await h.admin_with_token(client, "BILLING_ADMIN")
    d = (await client.get(f"{API}/admin/dashboard", headers=admin.headers)).json()
    assert d["orgs_total"] >= 1 and d["users_total"] >= 1 and d["irp_health"] == "ok"
    assert len(d["signups_series"]) == 30 and d["signups_series"][-1]["count"] >= 1
    assert isinstance(d["mrr_inr"], str) and d["recent_orgs"]
    hl = (await client.get(f"{API}/admin/system/health", headers=admin.headers)).json()
    assert hl["db"] == "ok" and hl["environment"] == "test" and hl["storage"] and hl["email"] and hl["tax_gateway"]
    tokens = (await client.get(f"{API}/admin/meta/template-tokens", headers=admin.headers)).json()
    names = {t["token"] for t in tokens}
    assert {"{{org.legal_name}}", "{{run.period}}", "{{step.qc_readings}}", "{{accounts.unit_cost}}"} <= names
