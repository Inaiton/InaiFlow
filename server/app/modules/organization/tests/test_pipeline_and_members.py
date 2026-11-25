import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.core.security import create_access_token
from tests import factories as f

API = f.API


async def test_org_context_owner_full(client, owner):
    r = await client.get(f"{API}/org/context", headers=owner.headers)
    body = r.json()
    assert r.status_code == 200 and body["is_owner"] and body["role_code"] == "ORG_OWNER"
    assert len(body["permissions"]) == 27 and set(body["permissions"].values()) == {"FULL"}
    assert set(body["enabled_modules"]) == {
        "accounts",
        "payroll",
        "operations",
        "documents",
        "tally_xml_sync",
        "irp_einvoice",
    }
    assert body["current_fy"]["label"].startswith("FY ") and body["impersonation"] is None


async def test_missing_or_bad_org_header(client, owner):
    assert (await client.get(f"{API}/org/context", headers=owner.user_headers)).status_code == 400
    h = {**owner.user_headers, "X-Organization-ID": "nope"}
    assert (await client.get(f"{API}/org/context", headers=h)).status_code == 400


async def test_non_member_forbidden_even_with_forged_org(client, owner):
    other = await f.org_with_owner(client)
    r = await client.get(f"{API}/organization/members", headers=owner.in_org(other.org_id).headers)
    assert r.status_code == 403 and r.json()["error"]["code"] == "FORBIDDEN"


async def test_expired_membership(client, owner):
    m = await f.add_member(owner.org_id, "ACCOUNTANT", access_expires_at=datetime.now(UTC) - timedelta(minutes=1))
    r = await client.get(f"{API}/org/context", headers=m.headers)
    assert r.status_code == 403 and r.json()["error"]["code"] == "MEMBERSHIP_EXPIRED"


async def test_suspended_org(client, owner):
    await f.set_org(owner.org_id, org_status="SUSPENDED")
    r = await client.get(f"{API}/org/context", headers=owner.headers)
    assert r.status_code == 403 and r.json()["error"]["code"] == "ORG_SUSPENDED"


async def test_suspended_membership(client, owner):
    m = await f.add_member(owner.org_id, "ACCOUNTANT", status="SUSPENDED")
    assert (await client.get(f"{API}/org/context", headers=m.headers)).status_code == 403


async def test_external_requires_mfa(client, owner):
    auditor = await f.add_member(owner.org_id, "AUDITOR")
    r = await client.get(f"{API}/org/context", headers=auditor.headers)
    assert r.status_code == 403 and r.json()["error"]["code"] == "MFA_REQUIRED"
    mfa_auditor = await f.add_member(owner.org_id, "AUDITOR", mfa=True)
    r = await client.get(f"{API}/org/context", headers=mfa_auditor.headers)
    assert r.status_code == 200 and r.json()["is_external"]
    assert r.json()["permissions"]["operations.runs_accounting"] == "NONE"


async def test_enforce_2fa_all(client, owner):
    acct = await f.add_member(owner.org_id, "ACCOUNTANT")
    sec = (await client.get(f"{API}/organization/security", headers=owner.headers)).json()
    sec["enforce_2fa_all"] = True
    r = await client.put(f"{API}/organization/security", json=sec, headers=owner.headers)
    assert r.status_code == 200 and r.json()["enforce_2fa_all"]
    assert (await client.get(f"{API}/org/context", headers=acct.headers)).json()["error"]["code"] == "MFA_REQUIRED"


@pytest.mark.parametrize(
    ("role", "path", "expected"),
    [
        ("OPERATOR", "/organization/members", 403),
        ("OPERATOR", "/organization/profile", 403),
        ("ACCOUNTANT", "/organization/audit-logs", 200),
        ("ACCOUNTANT", "/organization/members", 403),
        ("ACCOUNTANT", "/organization/profile", 200),
        ("ADMIN", "/organization/billing", 200),
        ("QA_LEAD", "/organization/roles", 403),
        ("ADMIN", "/organization/roles", 200),
        ("OPERATOR", "/org/context", 200),
    ],
)
async def test_permission_levels_per_role(client, owner, role, path, expected):
    m = await f.add_member(owner.org_id, role)
    r = await client.get(f"{API}{path}", headers=m.headers)
    assert r.status_code == expected, r.text
    if expected == 403:
        assert r.json()["error"]["code"] == "PERMISSION_DENIED"


async def test_admin_billing_read_but_profile_write(client, owner):
    admin = await f.add_member(owner.org_id, "ADMIN")
    r = await client.patch(f"{API}/organization/profile", json={"city": "Chennai"}, headers=admin.headers)
    assert r.status_code == 200 and r.json()["city"] == "Chennai"
    acct = await f.add_member(owner.org_id, "ACCOUNTANT")
    assert (
        await client.patch(f"{API}/organization/profile", json={"city": "X"}, headers=acct.headers)
    ).status_code == 403


async def test_profile_update_audited_and_state_validation(client, owner):
    r = await client.patch(
        f"{API}/organization/profile", json={"state_code": "27", "gstin": "27ABCDE1234F1Z5"}, headers=owner.headers
    )
    assert r.status_code == 200 and r.json()["state_name"] == "Maharashtra"
    bad = await client.patch(f"{API}/organization/profile", json={"gstin": "29ABCDE1234F1Z5"}, headers=owner.headers)
    assert bad.status_code == 400
    logs = (await client.get(f"{API}/organization/audit-logs", params={"entity_type": "organization", "action": "UPDATE"},
                             headers=owner.headers)).json()  # fmt: skip
    assert logs["total"] == 1 and logs["items"][0]["after_diff"]["state_code"] == "27"
    assert logs["items"][0]["before_diff"]["state_code"] == "33" and logs["items"][0]["user_name"] == "Olivia Owner"


async def test_branches_crud_single_head_office(client, owner):
    h = owner.headers
    a = (
        await client.post(f"{API}/organization/branches", json={"name": "Plant 1", "is_head_office": True}, headers=h)
    ).json()
    b = (
        await client.post(f"{API}/organization/branches", json={"name": "Plant 2", "is_head_office": True}, headers=h)
    ).json()
    rows = {x["id"]: x for x in (await client.get(f"{API}/organization/branches", headers=h)).json()}
    assert rows[b["id"]]["is_head_office"] and not rows[a["id"]]["is_head_office"]
    assert (await client.delete(f"{API}/organization/branches/{a['id']}", headers=h)).status_code == 204


async def test_invitation_accept_flow_with_acl_grants(client, owner, outbox):
    invitee = await f.create_user()
    rid = await f.role_id(owner.org_id, "ACCOUNTANT")
    folder = (await f.sql("SELECT id FROM doc_folders WHERE org_id=:o AND system_kind='MASTER_SOP'", o=owner.org_id))[
        0
    ][0]
    body = {
        "email": invitee.email.upper(),
        "role_id": str(rid),
        "acl_grants": [{"resource_type": "DOC_FOLDER", "resource_id": str(folder), "access_level": "NONE"}],
    }
    r = await client.post(f"{API}/organization/invitations", json=body, headers=owner.headers)
    assert r.status_code == 201 and r.json()["status"] == "PENDING" and r.json()["role_name"] == "Accountant"
    assert outbox.last_to(invitee.email, "INVITATION") is not None
    dup = await client.post(f"{API}/organization/invitations", json=body, headers=owner.headers)
    assert dup.status_code == 409
    mine = (await client.get(f"{API}/me/invitations", headers=invitee.user_headers)).json()
    assert len(mine) == 1 and mine[0]["invited_by_name"] == "Olivia Owner"
    acc = await client.post(f"{API}/me/invitations/{mine[0]['id']}/accept", headers=invitee.user_headers)
    assert acc.status_code == 200 and acc.json()["role_code"] == "ACCOUNTANT"
    orgs = (await client.get(f"{API}/me/organizations", headers=invitee.user_headers)).json()
    assert [o["org_id"] for o in orgs] == [str(owner.org_id)]
    acl = (
        await client.get(f"{API}/organization/acl", params={"subject_id": str(invitee.user_id)}, headers=owner.headers)
    ).json()
    assert acl[0]["resource_name"] == "ISO Quality Manual & Approved SOPs" and acl[0]["access_level"] == "NONE"
    again = await client.post(f"{API}/me/invitations/{mine[0]['id']}/accept", headers=invitee.user_headers)
    assert again.status_code == 409


async def test_invitation_decline_and_cancel(client, owner):
    invitee = await f.create_user()
    rid = await f.role_id(owner.org_id, "OPERATOR")
    inv = (await client.post(f"{API}/organization/invitations", json={"email": invitee.email, "role_id": str(rid)},
                             headers=owner.headers)).json()  # fmt: skip
    stranger = await f.create_user()
    assert (
        await client.post(f"{API}/me/invitations/{inv['id']}/accept", headers=stranger.user_headers)
    ).status_code == 404
    assert (
        await client.post(f"{API}/me/invitations/{inv['id']}/decline", headers=invitee.user_headers)
    ).status_code == 204
    inv2 = (await client.post(f"{API}/organization/invitations", json={"email": "later@example.com", "role_id": str(rid)},
                              headers=owner.headers)).json()  # fmt: skip
    assert (
        await client.post(f"{API}/organization/invitations/{inv2['id']}/resend", headers=owner.headers)
    ).status_code == 204
    assert (
        await client.delete(f"{API}/organization/invitations/{inv2['id']}", headers=owner.headers)
    ).status_code == 204
    listed = (
        await client.get(f"{API}/organization/invitations", params={"status": "CANCELLED"}, headers=owner.headers)
    ).json()
    assert [i["id"] for i in listed] == [inv2["id"]]


async def test_seat_quota(client, owner):
    await f.set_org(owner.org_id, quota_overrides={"max_internal_seats": 2})
    rid = await f.role_id(owner.org_id, "ACCOUNTANT")
    r1 = await client.post(
        f"{API}/organization/invitations", json={"email": "a1@example.com", "role_id": str(rid)}, headers=owner.headers
    )
    assert r1.status_code == 201
    r2 = await client.post(
        f"{API}/organization/invitations", json={"email": "a2@example.com", "role_id": str(rid)}, headers=owner.headers
    )
    assert r2.status_code == 403 and r2.json()["error"]["code"] == "QUOTA_EXCEEDED"
    billing = (await client.get(f"{API}/organization/billing", headers=owner.headers)).json()
    assert (
        billing["internal_seats_used"] == 1
        and billing["internal_seats_max"] == 2
        and billing["plan_code"] == "FREE_TRIAL"
    )


async def test_join_request_flow(client, owner, outbox):
    user = await f.create_user()
    code = owner.extra["org"]["public_join_code"]
    r = await client.post(
        f"{API}/me/join-requests", json={"join_code": code.lower(), "message": "CA for FY26"}, headers=user.user_headers
    )
    assert r.status_code == 201 and r.json()["status"] == "PENDING"
    assert (
        await client.post(f"{API}/me/join-requests", json={"join_code": code}, headers=user.user_headers)
    ).status_code == 409
    reqs = (await client.get(f"{API}/organization/join-requests", headers=owner.headers)).json()
    assert reqs[0]["message"] == "CA for FY26" and reqs[0]["is_email_verified"]
    rid = await f.role_id(owner.org_id, "ACCOUNTANT")
    m = await client.post(
        f"{API}/organization/join-requests/{reqs[0]['id']}/approve", json={"role_id": str(rid)}, headers=owner.headers
    )
    assert m.status_code == 200 and m.json()["role_code"] == "ACCOUNTANT"
    mine = (await client.get(f"{API}/me/join-requests", headers=user.user_headers)).json()
    assert mine[0]["status"] == "ACCEPTED"
    assert (await client.get(f"{API}/org/context", headers=user.in_org(owner.org_id).headers)).status_code == 200


async def test_join_request_reject_and_cancel(client, owner):
    a, b = await f.create_user(), await f.create_user()
    code = owner.extra["org"]["public_join_code"]
    ra = (await client.post(f"{API}/me/join-requests", json={"join_code": code}, headers=a.user_headers)).json()
    rb = (await client.post(f"{API}/me/join-requests", json={"join_code": code}, headers=b.user_headers)).json()
    assert (
        await client.post(f"{API}/organization/join-requests/{ra['id']}/reject", headers=owner.headers)
    ).status_code == 204
    assert (await client.delete(f"{API}/me/join-requests/{rb['id']}", headers=b.user_headers)).status_code == 204
    assert (
        await client.post(f"{API}/me/join-requests", json={"join_code": "ORG-0000000"}, headers=a.user_headers)
    ).status_code == 404


async def test_owner_protected_and_member_management(client, owner):
    members = (await client.get(f"{API}/organization/members", headers=owner.headers)).json()
    me = next(m for m in members if m["is_owner"])
    admin = await f.add_member(owner.org_id, "ADMIN")
    r = await client.patch(
        f"{API}/organization/members/{me['membership_id']}", json={"status": "SUSPENDED"}, headers=admin.headers
    )
    assert r.status_code == 409 and r.json()["error"]["code"] == "SYSTEM_RECORD"
    assert (
        await client.delete(f"{API}/organization/members/{me['membership_id']}", headers=admin.headers)
    ).status_code == 409
    op = await f.add_member(owner.org_id, "OPERATOR")
    qa = await f.role_id(owner.org_id, "QA_LEAD")
    r = await client.patch(
        f"{API}/organization/members/{op.membership_id}", json={"role_id": str(qa)}, headers=admin.headers
    )
    assert r.status_code == 200 and r.json()["role_code"] == "QA_LEAD"
    owner_role = await f.role_id(owner.org_id, "ORG_OWNER")
    r = await client.patch(
        f"{API}/organization/members/{op.membership_id}", json={"role_id": str(owner_role)}, headers=admin.headers
    )
    assert r.status_code == 400
    assert (
        await client.delete(f"{API}/organization/members/{op.membership_id}", headers=admin.headers)
    ).status_code == 204
    assert (await client.get(f"{API}/org/context", headers=op.headers)).status_code == 403
    found = (await client.get(f"{API}/organization/members", params={"q": "qa_lead"}, headers=owner.headers)).json()
    assert found == []


async def test_transfer_ownership(client, owner):
    admin = await f.add_member(owner.org_id, "ADMIN")
    bad = await client.post(f"{API}/organization/transfer-ownership", json={"membership_id": str(admin.membership_id), "password": "wrong-password"},
                            headers=owner.headers)  # fmt: skip
    assert bad.status_code == 401
    not_owner = await client.post(f"{API}/organization/transfer-ownership", json={"membership_id": str(owner.membership_id), "password": f.PASSWORD},
                                  headers=admin.headers)  # fmt: skip
    assert not_owner.status_code == 403
    r = await client.post(f"{API}/organization/transfer-ownership", json={"membership_id": str(admin.membership_id), "password": f.PASSWORD},
                          headers=owner.headers)  # fmt: skip
    assert r.status_code == 204
    assert (await client.get(f"{API}/org/context", headers=admin.headers)).json()["is_owner"] is True
    ctx = (await client.get(f"{API}/org/context", headers=owner.headers)).json()
    assert ctx["role_code"] == "ADMIN" and not ctx["is_owner"]


async def test_check_slug_and_duplicate(client, owner):
    slug = owner.extra["org"]["workspace_slug"]
    assert (
        await client.get(f"{API}/organizations/check-slug", params={"slug": slug}, headers=owner.user_headers)
    ).json() == {"ok": False}
    assert (
        await client.get(f"{API}/organizations/check-slug", params={"slug": "admin"}, headers=owner.user_headers)
    ).json() == {"ok": False}
    assert (
        await client.get(
            f"{API}/organizations/check-slug", params={"slug": f.unique("free-")}, headers=owner.user_headers
        )
    ).json() == {"ok": True}
    r = await client.post(f"{API}/organizations", json=f.org_payload(workspace_slug=slug), headers=owner.user_headers)
    assert r.status_code == 409
    r = await client.post(
        f"{API}/organizations", json=f.org_payload(workspace_slug="Bad Slug"), headers=owner.user_headers
    )
    assert r.status_code == 422


async def test_union_territory_uses_utgst(client):
    o = await f.org_with_owner(client, state_code="04", gstin=None, city="Chandigarh")
    names = {
        r[0]
        for r in await f.sql(
            "SELECT name FROM ledgers WHERE org_id=:o AND system_code IN ('SGST_OUT','SGST_IN')", o=o.org_id
        )
    }
    assert names == {"Output UTGST", "Input UTGST"}


async def test_impersonation_read_only(client, owner):
    admin_id = (await f.sql("INSERT INTO platform_admins (email, password_hash, full_name, role) VALUES (:e, 'x', 'Support Sam', 'SUPPORT_ADMIN') RETURNING id",
                            e=f"{f.unique('a')}@inaiflow.test"))[0][0]  # fmt: skip
    sid = (await f.sql("INSERT INTO platform_impersonation_sessions (admin_id, org_id, mode, ticket_reference, reason, expires_at) "
                       "VALUES (:a, :o, 'READ_ONLY', 'T-1', 'debug', now() + interval '30 minutes') RETURNING id",
                       a=admin_id, o=owner.org_id))[0][0]  # fmt: skip
    from app.core.security import create_impersonation_token

    tok = create_impersonation_token(admin_id=admin_id, session_id=sid, org_id=owner.org_id, mode="READ_ONLY",
                                     expires_at=datetime.now(UTC) + timedelta(minutes=30))  # fmt: skip
    h = {"Authorization": f"Bearer {tok}", "X-Organization-ID": str(owner.org_id)}
    ctx = (await client.get(f"{API}/org/context", headers=h)).json()
    assert ctx["role_code"] == "SUPPORT_IMPERSONATION" and ctx["impersonation"]["admin_name"] == "Support Sam"
    assert set(ctx["permissions"].values()) == {"READ"}
    r = await client.patch(f"{API}/organization/profile", json={"city": "X"}, headers=h)
    assert r.status_code == 403 and r.json()["error"]["code"] == "FORBIDDEN"
    assert (await client.get(f"{API}/me", headers={"Authorization": f"Bearer {tok}"})).status_code == 403
    other = await f.org_with_owner(client)
    assert (
        await client.get(f"{API}/org/context", headers={**h, "X-Organization-ID": str(other.org_id)})
    ).status_code == 403


async def test_impersonation_full_support_audited(client, owner):
    admin_id = (await f.sql("INSERT INTO platform_admins (email, password_hash, full_name) VALUES (:e, 'x', 'Sup') RETURNING id",
                            e=f"{f.unique('a')}@inaiflow.test"))[0][0]  # fmt: skip
    sid = (await f.sql("INSERT INTO platform_impersonation_sessions (admin_id, org_id, mode, ticket_reference, reason, expires_at) "
                       "VALUES (:a, :o, 'FULL_SUPPORT', 'T-2', 'fix', now() + interval '30 minutes') RETURNING id",
                       a=admin_id, o=owner.org_id))[0][0]  # fmt: skip
    from app.core.security import create_impersonation_token

    tok = create_impersonation_token(admin_id=admin_id, session_id=sid, org_id=owner.org_id, mode="FULL_SUPPORT",
                                     expires_at=datetime.now(UTC) + timedelta(minutes=30))  # fmt: skip
    h = {"Authorization": f"Bearer {tok}", "X-Organization-ID": str(owner.org_id)}
    assert (await client.patch(f"{API}/organization/profile", json={"city": "Madurai"}, headers=h)).status_code == 200
    assert (await client.get(f"{API}/organization/roles", headers=h)).status_code == 200
    rid = await f.role_id(owner.org_id, "OPERATOR")
    r = await client.post(
        f"{API}/organization/invitations", json={"email": "x@example.com", "role_id": str(rid)}, headers=h
    )
    assert r.status_code == 403  # organization.members is READ for support
    plat = await f.sql("SELECT action FROM platform_audit_logs WHERE superadmin_id=:a", a=admin_id)
    assert len(plat) >= 2 and all(p[0] == "IMPERSONATED_REQUEST" for p in plat)
    audit = await f.sql(
        "SELECT actor_type, actor_id, user_id FROM org_audit_logs WHERE org_id=:o AND entity_type='organization' AND action='UPDATE'",
        o=owner.org_id,
    )
    assert audit[0] == ("PLATFORM_ADMIN", admin_id, None)
    await f.sql("UPDATE platform_impersonation_sessions SET ended_at=now() WHERE id=:s", s=sid)
    assert (await client.get(f"{API}/org/context", headers=h)).status_code == 401


async def test_token_for_unknown_session_rejected(client, owner):
    tok, _ = create_access_token(user_id=owner.user_id, session_id=uuid.uuid4(), email=owner.email, mfa=False)
    r = await client.get(
        f"{API}/org/context", headers={"Authorization": f"Bearer {tok}", "X-Organization-ID": str(owner.org_id)}
    )
    assert r.status_code == 401
