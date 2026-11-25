from tests import factories as f

API = f.API


async def test_health(client):
    r = await client.get(f"{API}/health")
    assert r.status_code == 200 and r.json()["db"] == "ok"


async def test_create_org_seeds_everything(client, owner):
    org = owner.extra["org"]
    assert org["role_code"] == "ORG_OWNER" and org["public_join_code"].startswith("ORG-")
    oid = owner.org_id
    groups = await f.sql(
        "SELECT count(*), count(*) FILTER (WHERE parent_group_id IS NULL) FROM account_groups WHERE org_id=:o", o=oid
    )
    assert groups[0] == (28, 15)
    codes = {
        r[0] for r in await f.sql("SELECT system_code FROM ledgers WHERE org_id=:o AND system_code IS NOT NULL", o=oid)
    }
    assert {
        "CASH",
        "SALES",
        "CGST_OUT",
        "SGST_IN",
        "ROUND_OFF",
        "SALARY_PAYABLE",
        "STOCK_FG",
        "FOREX_GAIN_LOSS",
    } <= codes
    assert len(codes) == 28
    roles = {r[0] for r in await f.sql("SELECT role_code FROM org_roles WHERE org_id=:o", o=oid)}
    assert roles == {"ORG_OWNER", "ADMIN", "ACCOUNTANT", "QA_LEAD", "OPERATOR", "AUDITOR"}
    godowns = {r[0] for r in await f.sql("SELECT system_code FROM godowns WHERE org_id=:o AND is_system", o=oid)}
    assert godowns == {"MAIN", "WIP", "SCRAP", "FG"}
    vts = await f.sql(
        "SELECT count(*), count(*) FILTER (WHERE NOT is_accounting) FROM voucher_types WHERE org_id=:o", o=oid
    )
    assert vts[0][0] == 25 and vts[0][1] >= 14
    folders = await f.sql("SELECT system_kind, name, is_system_locked FROM doc_folders WHERE org_id=:o", o=oid)
    kinds = {r[0] for r in folders}
    assert {"FY_ROOT", "MONTH", "BILLS", "OPERATIONS", "PAYROLL", "MASTER_LIBRARY", "MASTER_SOP"} <= kinds
    assert all(r[2] for r in folders)
    assert (await f.sql("SELECT count(*) FROM doc_templates WHERE org_id=:o AND is_system_default", o=oid))[0][0] == 5
    assert (await f.sql("SELECT count(*) FROM iso_checklist_items WHERE org_id=:o", o=oid))[0][0] >= 30
    assert (await f.sql("SELECT pt_state_code FROM payroll_settings WHERE org_id=:o", o=oid))[0][0] == "33"
    audit = await f.sql("SELECT action, entity_type FROM org_audit_logs WHERE org_id=:o", o=oid)
    assert ("CREATE", "organization") in audit
