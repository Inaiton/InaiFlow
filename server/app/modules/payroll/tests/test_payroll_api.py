"""Payroll API: employees, settings, attendance, runs, lock (with interface fakes + real-interface variant), files,
permissions and tenant isolation."""

from __future__ import annotations

import json
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import text

from app.modules.accounts import interface as accounts_if
from app.modules.documents import interface as documents_if
from app.modules.operations import interface as operations_if
from tests import factories
from tests.factories import API

P = f"{API}/accounts/payroll"
MONTH = "2026-09"
D = Decimal


def emp(code: str | None = None, **kw) -> dict:
    body = {
        "emp_code": code or factories.unique("E"), "full_name": "Ravi Kumar", "date_of_joining": "2026-04-01",
        "pan": "ABCDE1234F", "uan_epf": "100200300400", "esic_ip_no": "3100123456", "bank_account_no": "50100012345678",
        "bank_ifsc": "HDFC0001234", "employee_category": "STAFF",
        "salary_structure": {"basic": "15000", "hra": "5000", "epf_applicable": True, "esic_applicable": True,
                             "pt_applicable": True},
    }  # fmt: skip
    body.update(kw)
    return body


async def create_emp(client, actor, **kw) -> dict:
    r = await client.post(f"{P}/employees", json=emp(**kw), headers=actor.headers)
    assert r.status_code == 201, r.text
    return r.json()


async def finalize(client, actor, rows: list[dict]) -> dict:
    r = await client.put(f"{P}/attendance", json={"month": MONTH, "rows": rows}, headers=actor.headers)
    assert r.status_code == 200, r.text
    return r.json()


def row(e: dict, **kw) -> dict:
    base = {"employee_id": e["id"], "days_present": "30", "lop_days": "0", "finalized": True}
    base.update(kw)
    return base


async def custom_role_member(org_id, perms: dict) -> factories.Actor:
    code = factories.unique("R").upper()
    await factories.sql(
        "INSERT INTO org_roles (org_id, role_code, role_name, permissions) VALUES (:o, :c, :c, CAST(:p AS jsonb))",
        o=org_id,
        c=code,
        p=json.dumps(perms),
    )
    return await factories.add_member(org_id, code)


# ----------------------------------------------------------------- fakes for S2/S4 interfaces
class Fakes:
    def __init__(self) -> None:
        self.vouchers: list[dict] = []
        self.allocations: list[tuple[uuid.UUID, Decimal]] = []
        self.files: list[dict] = []
        self.runs: dict[uuid.UUID, uuid.UUID | None] = {}


@pytest.fixture
def fakes(monkeypatch) -> Fakes:
    f = Fakes()

    async def post_system_voucher(db, ctx, *, base_type, voucher_date, entries, narration, **kw):
        vid = (await db.execute(text(
            "INSERT INTO vouchers (org_id, voucher_type_id, voucher_number, voucher_date, status, total_amount, "
            "narration, created_by) SELECT :o, id, :n, :d, 'REGULAR', 0, :nar, :u FROM voucher_types "
            "WHERE org_id = :o AND base_type = :b LIMIT 1 RETURNING id"),
            {"o": ctx.org_id, "n": factories.unique("V"), "d": voucher_date, "nar": narration, "u": ctx.user_id,
             "b": base_type})).scalar_one()  # fmt: skip
        f.vouchers.append({"id": vid, "base_type": base_type, "date": voucher_date, "entries": list(entries)})
        return vid

    async def resource_names(db, ctx, resource_type, ids):
        return {i: "Run" for i in ids if i in f.runs}

    async def get_runs_by_ids(db, ctx, ids):
        return [{"id": i, "cost_centre_id": f.runs[i]} for i in ids if i in f.runs]

    async def apply_payroll_allocation(db, ctx, run_id, amount):
        f.allocations.append((run_id, amount))

    async def store_generated_file(db, ctx, *, folder_id, title, mime, data, source_type, **kw):
        f.files.append({"folder_id": folder_id, "title": title, "mime": mime, "data": data, "source": source_type})
        return uuid.uuid4()

    monkeypatch.setattr(accounts_if, "post_system_voucher", post_system_voucher)
    monkeypatch.setattr(operations_if, "resource_names", resource_names)
    monkeypatch.setattr(operations_if, "get_runs_by_ids", get_runs_by_ids)
    monkeypatch.setattr(operations_if, "apply_payroll_allocation", apply_payroll_allocation)
    monkeypatch.setattr(documents_if, "store_generated_file", store_generated_file)
    return f


# ----------------------------------------------------------------- employees
async def test_employee_crud_and_validation(client, owner):
    e = await create_emp(client, owner, emp_code="EMP-001", pan="abcde1234f")
    assert e["pan"] == "ABCDE1234F" and e["monthly_gross"] == "20000.00" and e["tax_regime"] == "NEW"
    assert e["salary_structure"]["basic"] == "15000.00"

    r = await client.post(f"{P}/employees", json=emp("emp-001"), headers=owner.headers)
    assert r.status_code == 409 and r.json()["error"]["code"] == "ALREADY_EXISTS"
    r = await client.post(f"{P}/employees", json=emp(pan="12345"), headers=owner.headers)
    assert r.status_code == 422
    r = await client.post(f"{P}/employees", json=emp(bank_ifsc="HDFC1234567"), headers=owner.headers)
    assert r.status_code == 422
    r = await client.post(f"{P}/employees", json=emp(employee_category="BOSS"), headers=owner.headers)
    assert r.status_code == 422
    stranger = await factories.create_user()
    r = await client.post(f"{P}/employees", json=emp(user_id=str(stranger.user_id)), headers=owner.headers)
    assert r.status_code == 400

    body = emp("EMP-001", full_name="Ravi K", salary_structure={**emp()["salary_structure"], "basic": "18000"})
    r = await client.patch(f"{P}/employees/{e['id']}", json=body, headers=owner.headers)
    assert r.status_code == 200 and r.json()["monthly_gross"] == "23000.00" and r.json()["full_name"] == "Ravi K"

    r = await client.get(f"{P}/employees", params={"q": "ravi"}, headers=owner.headers)
    assert r.json()["total"] == 1

    acct = await factories.add_member(owner.org_id, "ACCOUNTANT")
    r = await client.post(f"{P}/employees/{e['id']}/exit", json={"date_of_exit": "2026-10-15"}, headers=acct.headers)
    assert r.status_code == 403  # exit needs FULL; accountant has WRITE
    r = await client.post(f"{P}/employees/{e['id']}/exit", json={"date_of_exit": "2026-10-15"}, headers=owner.headers)
    assert r.status_code == 200 and r.json()["is_active"] is False
    r = await client.get(f"{P}/employees", headers=owner.headers)
    assert r.json()["total"] == 0
    r = await client.get(f"{P}/employees", params={"include_exited": "true"}, headers=owner.headers)
    assert r.json()["total"] == 1
    audit = await factories.sql("SELECT action FROM org_audit_logs WHERE entity_id = :e", e=uuid.UUID(e["id"]))
    assert {a[0] for a in audit} == {"CREATE", "UPDATE"}


async def test_settings_get_put(client, owner):
    r = await client.get(f"{P}/settings", headers=owner.headers)
    assert r.status_code == 200 and r.json()["pt_state_code"] == "33" and r.json()["working_days_basis"] == "CALENDAR"
    cash = (await factories.sql("SELECT id FROM ledgers WHERE org_id = :o AND system_code = 'CASH'", o=owner.org_id))[
        0
    ][0]
    r = await client.put(f"{P}/settings", json={"working_days_basis": "FIXED_26", "default_bank_ledger_id": str(cash),
                                                "pt_state_code": "27"}, headers=owner.headers)  # fmt: skip
    assert r.status_code == 200, r.text
    assert r.json()["working_days_basis"] == "FIXED_26" and r.json()["default_bank_ledger_id"] == str(cash)

    other = await factories.org_with_owner(client)
    foreign = (
        await factories.sql("SELECT id FROM ledgers WHERE org_id = :o AND system_code = 'CASH'", o=other.org_id)
    )[0][0]
    r = await client.put(f"{P}/settings", json={"default_bank_ledger_id": str(foreign)}, headers=owner.headers)
    assert r.status_code == 400 and r.json()["error"]["details"]["ledger_ids"] == [str(foreign)]
    r = await client.put(f"{P}/settings", json={"pt_state_code": "99"}, headers=owner.headers)
    assert r.status_code == 400
    r = await client.put(f"{P}/settings", json={"working_days_basis": "WEEKLY"}, headers=owner.headers)
    assert r.status_code == 422
    acct = await factories.add_member(owner.org_id, "ACCOUNTANT")
    assert (await client.get(f"{P}/settings", headers=acct.headers)).status_code == 200


# ----------------------------------------------------------------- attendance
async def test_attendance_defaults_upsert_and_validation(client, owner, fakes):
    staff = await create_emp(client, owner)
    joiner = await create_emp(client, owner, date_of_joining="2026-09-11")
    op = await create_emp(client, owner, employee_category="SHOP_FLOOR_OPERATOR")
    await create_emp(client, owner, date_of_joining="2026-10-01")  # not on rolls in September

    r = await client.get(f"{P}/attendance", params={"month": MONTH}, headers=owner.headers)
    assert r.status_code == 200
    rows = {x["employee_id"]: x for x in r.json()["rows"]}
    assert len(rows) == 3 and r.json()["all_finalized"] is False
    assert rows[staff["id"]]["days_present"] == "30.00" and rows[staff["id"]]["days_in_month"] == 30
    assert rows[joiner["id"]]["lop_days"] == "10.00" and rows[joiner["id"]]["days_present"] == "20.00"

    run_a, run_b = uuid.uuid4(), uuid.uuid4()
    fakes.runs.update({run_a: uuid.uuid4(), run_b: None})
    alloc = [{"period_run_id": str(run_a), "share_pct": "60"}, {"period_run_id": str(run_b), "share_pct": "40"}]
    out = await finalize(client, owner, [row(staff, lop_days="2", days_present="28", finalized=False),
                                         row(op, overtime_hours="4", run_allocations=alloc)])  # fmt: skip
    rows = {x["employee_id"]: x for x in out["rows"]}
    assert rows[staff["id"]]["lop_days"] == "2.00" and rows[staff["id"]]["finalized"] is False
    assert rows[op["id"]]["run_allocations"][0]["share_pct"] == "60.00" and rows[op["id"]]["finalized"] is True

    bad = [
        [row(staff, run_allocations=alloc)],  # non-operator
        [row(op, run_allocations=[{"period_run_id": str(run_a), "share_pct": "50"}])],  # != 100
        [row(op, run_allocations=[{"period_run_id": str(uuid.uuid4()), "share_pct": "100"}])],  # unknown run
        [row(staff, days_present="30", lop_days="2")],  # > days in month
        [{"employee_id": str(uuid.uuid4()), "days_present": "30", "lop_days": "0"}],
    ]
    for rows_in in bad:
        r = await client.put(f"{P}/attendance", json={"month": MONTH, "rows": rows_in}, headers=owner.headers)
        assert r.status_code == 400, (rows_in, r.text)
    r = await client.get(f"{P}/attendance", params={"month": "2026-13"}, headers=owner.headers)
    assert r.status_code == 422


async def test_pull_operations_suggests_shares(client, owner, monkeypatch):
    user = await factories.add_member(owner.org_id, "OPERATOR")
    op = await create_emp(client, owner, employee_category="SHOP_FLOOR_OPERATOR", user_id=str(user.user_id))
    run_a, run_b = uuid.uuid4(), uuid.uuid4()
    execs = [{"period_run_id": run_a, "executed_by": user.user_id}] * 3 + [
        {"period_run_id": run_b, "executed_by": user.user_id},
        {"period_run_id": run_b, "executed_by": uuid.uuid4()},
    ]

    async def list_execs(db, ctx, month):
        return execs

    monkeypatch.setattr(operations_if, "list_step_executions_by_month", list_execs)
    r = await client.post(f"{P}/attendance/pull-operations", params={"month": MONTH}, headers=owner.headers)
    assert r.status_code == 200, r.text
    (op_row,) = [x for x in r.json()["rows"] if x["employee_id"] == op["id"]]
    assert op_row["run_allocations"] == [{"period_run_id": str(run_a), "share_pct": "75.00"},
                                         {"period_run_id": str(run_b), "share_pct": "25.00"}]  # fmt: skip
    assert op_row["finalized"] is False


# ----------------------------------------------------------------- runs
async def test_run_create_recompute_delete_and_not_ready(client, owner):
    a = await create_emp(client, owner, emp_code="A1")
    await create_emp(client, owner, emp_code="B1")
    r = await client.post(f"{P}/runs", json={"month": MONTH}, headers=owner.headers)
    assert r.status_code == 201, r.text
    run = r.json()
    assert run["status"] == "DRAFT" and run["employee_count"] == 2
    line = run["lines"][0]
    # TN PT: 1.2L half-yearly -> 1250 / 6 = 208.33 per month; EPF 1800; ESIC ceil(150)
    assert line["gross"] == "20000.00"
    assert line["deductions_breakdown"] == {"epf": "1800.00", "esic": "150.00", "pt": "208.33"}
    assert line["net_pay"] == "17841.67"
    assert run["total_gross"] == "40000.00"
    # admin minimum 500: 2 x 75 computed + 350 top-up on the first line
    assert D(run["total_employer_contrib"]) == 2 * (1250 + 550 + 75 + D("650")) + 500

    assert (await client.post(f"{P}/runs", json={"month": MONTH}, headers=owner.headers)).status_code == 409

    r = await client.post(f"{P}/runs/{run['id']}/lock", headers=owner.headers)
    assert r.status_code == 409 and r.json()["error"]["code"] == "PAYROLL_NOT_READY"
    assert {m["emp_code"] for m in r.json()["error"]["details"]["missing"]} == {"A1", "B1"}
    await finalize(client, owner, [row(a, lop_days="3", days_present="27")])
    r = await client.post(f"{P}/runs/{run['id']}/lock", headers=owner.headers)
    assert [m["emp_code"] for m in r.json()["error"]["details"]["missing"]] == ["B1"]

    r = await client.post(f"{P}/runs/{run['id']}/recompute", headers=owner.headers)
    assert r.status_code == 200
    line_a = next(x for x in r.json()["lines"] if x["emp_code"] == "A1")
    assert line_a["earnings_breakdown"] == {"basic": "13500.00", "hra": "4500.00"} and line_a["lop_days"] == "3.00"

    r = await client.delete(f"{P}/runs/{run['id']}", headers=owner.headers)
    assert r.status_code == 204
    assert (await client.get(f"{P}/runs/{run['id']}", headers=owner.headers)).status_code == 404


async def test_permissions(client, owner, fakes):
    await create_emp(client, owner)
    operator = await factories.add_member(owner.org_id, "OPERATOR")
    for method, url in (("GET", f"{P}/runs"), ("GET", f"{P}/employees"), ("GET", f"{P}/settings")):
        assert (await client.request(method, url, headers=operator.headers)).status_code == 403
    acct = await factories.add_member(owner.org_id, "ACCOUNTANT")
    r = await client.post(f"{P}/runs", json={"month": MONTH}, headers=acct.headers)
    assert r.status_code == 201
    run_id = r.json()["id"]
    assert (await client.get(f"{P}/runs", headers=acct.headers)).json()[0]["id"] == run_id
    writer = await custom_role_member(owner.org_id, {"accounts.payroll_runs": "WRITE"})
    assert (await client.post(f"{P}/runs/{run_id}/recompute", headers=writer.headers)).status_code == 200
    assert (await client.post(f"{P}/runs/{run_id}/lock", headers=writer.headers)).status_code == 403
    assert (await client.delete(f"{P}/runs/{run_id}", headers=writer.headers)).status_code == 403
    assert (await client.get(f"{P}/runs/{run_id}/bank-file", headers=writer.headers)).status_code == 403

    other = await factories.org_with_owner(client)
    assert (await client.get(f"{P}/runs/{run_id}", headers=other.headers)).status_code == 404
    assert (await client.post(f"{P}/runs/{run_id}/lock", headers=other.headers)).status_code == 404


async def _locked_run(client, owner, fakes) -> tuple[dict, dict]:
    cc = uuid.uuid4()
    run_a, run_b = uuid.uuid4(), uuid.uuid4()
    fakes.runs.update({run_a: cc, run_b: None})
    staff = await create_emp(client, owner, emp_code="S1", full_name="=Staff One")
    op = await create_emp(client, owner, emp_code="O1", employee_category="SHOP_FLOOR_OPERATOR",
                          salary_structure={"basic": "12000", "da": "2000", "piece_rate": "1.50",
                                            "other_deductions": [{"name": "Canteen", "amount": "250"}],
                                            "epf_applicable": True, "esic_applicable": True,
                                            "pt_applicable": True})  # fmt: skip
    mgr = await create_emp(client, owner, emp_code="M1", employee_category="MANAGEMENT", esic_ip_no=None,
                           salary_structure={"basic": "300000", "epf_applicable": False, "esic_applicable": False,
                                             "pt_applicable": True})  # fmt: skip
    alloc = [{"period_run_id": str(run_a), "share_pct": "70"}, {"period_run_id": str(run_b), "share_pct": "30"}]
    await finalize(client, owner, [row(staff), row(op, production_units="1000", overtime_hours="2",
                                                   run_allocations=alloc), row(mgr)])  # fmt: skip
    r = await client.post(f"{P}/runs", json={"month": MONTH}, headers=owner.headers)
    assert r.status_code == 201
    r = await client.post(f"{P}/runs/{r.json()['id']}/lock", headers={**owner.headers, "Idempotency-Key": "lock-1"})
    assert r.status_code == 200, r.text
    return r.json(), {"cc": cc, "run_a": run_a, "run_b": run_b}


async def test_lock_posts_balanced_voucher_allocates_and_files_payslips(client, owner, fakes):
    run, ids = await _locked_run(client, owner, fakes)
    assert run["status"] == "LOCKED_POSTED" and run["locked_by_name"] == "Olivia Owner" and run["locked_at"]
    lines = {ln["emp_code"]: ln for ln in run["lines"]}
    op = lines["O1"]
    # operator: 12000 + 2000 + OT (14000/30/8*2*2 = 233.33) + piece 1500 = 15733.33
    assert op["earnings_breakdown"]["overtime"] == "233.33" and op["gross"] == "15733.33"
    assert op["period_run_allocations"] == [
        {"period_run_id": str(ids["run_a"]), "share_pct": "70.00", "amount": "11013.33"},
        {"period_run_id": str(ids["run_b"]), "share_pct": "30.00", "amount": "4720.00"}]  # fmt: skip
    assert sorted(fakes.allocations) == sorted([(ids["run_a"], D("11013.33")), (ids["run_b"], D("4720.00"))])

    (v,) = fakes.vouchers
    assert v["base_type"] == "PAYROLL" and str(v["id"]) == run["posted_voucher_id"] and str(v["date"]) == "2026-09-30"
    dr = sum(e.amount for e in v["entries"] if e.entry_type == "DR")
    cr = sum(e.amount for e in v["entries"] if e.entry_type == "CR")
    assert dr == cr == D(run["total_gross"]) + D(run["total_employer_contrib"])
    s = (await client.get(f"{P}/settings", headers=owner.headers)).json()
    by = {}
    for e in v["entries"]:
        by.setdefault((str(e.ledger_id), e.entry_type), []).append(e)
    direct = {e.cost_centre_id: e.amount for e in by[(s["direct_wages_ledger_id"], "DR")]}
    assert direct == {ids["cc"]: D("11013.33"), None: D("4720.00")}
    assert by[(s["admin_salary_ledger_id"], "DR")][0].amount == D(lines["S1"]["gross"]) + D(lines["M1"]["gross"])
    net_plus_other = sum(D(ln["net_pay"]) for ln in run["lines"]) + D("250")
    assert by[(s["salary_payable_ledger_id"], "CR")][0].amount == net_plus_other
    tds = by[(s["tds_payable_ledger_id"], "CR")][0].amount
    assert tds == D(lines["M1"]["deductions_breakdown"]["tds"]) > 0

    assert len(fakes.files) == 3 and all(
        f["source"] == "AUTO_PAYSLIP" and f["data"][:4] == b"%PDF" for f in fakes.files
    )
    folder = await factories.sql("SELECT name FROM doc_folders WHERE id = :f", f=fakes.files[0]["folder_id"])
    assert folder[0][0] == "Payroll & Statutory Challans"
    assert all(ln["payslip_document_id"] for ln in run["lines"])

    r = await client.post(f"{P}/runs/{run['id']}/lock", headers={**owner.headers, "Idempotency-Key": "lock-1"})
    assert r.status_code == 200 and r.headers.get("Idempotent-Replayed") == "true"
    assert (await client.post(f"{P}/runs/{run['id']}/lock", headers=owner.headers)).status_code == 409
    assert (await client.post(f"{P}/runs/{run['id']}/recompute", headers=owner.headers)).status_code == 409
    assert (await client.delete(f"{P}/runs/{run['id']}", headers=owner.headers)).status_code == 409
    r = await client.put(f"{P}/attendance", json={"month": MONTH, "rows": []}, headers=owner.headers)
    assert r.status_code == 409
    audit = await factories.sql("SELECT module FROM org_audit_logs WHERE entity_id = :e AND action = 'LOCK'",
                                e=uuid.UUID(run["id"]))  # fmt: skip
    assert audit == [("ACCOUNTS",)]

    # YTD feeds next month's TDS projection
    r = await client.post(f"{P}/runs", json={"month": "2026-10"}, headers=owner.headers)
    m1_oct = next(ln for ln in r.json()["lines"] if ln["emp_code"] == "M1")
    assert m1_oct["deductions_breakdown"]["tds"] == lines["M1"]["deductions_breakdown"]["tds"]


async def test_files_and_mark_paid(client, owner, fakes):
    run, _ = await _locked_run(client, owner, fakes)
    lines = {ln["emp_code"]: ln for ln in run["lines"]}

    r = await client.get(f"{P}/runs/{run['id']}/bank-file", headers=owner.headers)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    csv_rows = r.text.strip().split("\r\n")
    assert csv_rows[0] == "Beneficiary Name,Beneficiary Account Number,IFSC,Amount,Narration"
    assert len(csv_rows) == 4
    assert f"'=Staff One,50100012345678,HDFC0001234,{lines['S1']['net_pay']},Salary September 2026" in csv_rows

    r = await client.get(f"{P}/runs/{run['id']}/statutory/epf-ecr", headers=owner.headers)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/plain")
    ecr = r.text.strip().split("\n")
    assert len(ecr) == 2  # manager not in EPF
    assert "100200300400#~#=Staff One#~#20000#~#15000#~#15000#~#15000#~#1800#~#1250#~#550#~#0#~#0" in ecr

    r = await client.get(f"{P}/runs/{run['id']}/statutory/esic", headers=owner.headers)
    esic = r.text.strip().split("\r\n")
    assert esic[0].startswith("IP Number") and len(esic) == 3
    assert "3100123456,'=Staff One,30.00,20000.00" in esic

    r = await client.get(f"{P}/runs/{run['id']}/statutory/pt", headers=owner.headers)
    pt = r.text.strip().split("\r\n")
    assert pt[-1].startswith("TOTAL") and len(pt) == 5
    assert (await client.get(f"{P}/runs/{run['id']}/statutory/gst", headers=owner.headers)).status_code == 404

    r = await client.get(f"{P}/runs/{run['id']}/payslips/{lines['S1']['id']}", headers=owner.headers)
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf" and r.content[:4] == b"%PDF"
    assert (await client.get(f"{P}/runs/{run['id']}/payslips/{uuid.uuid4()}", headers=owner.headers)).status_code == 404

    s = (await client.get(f"{P}/settings", headers=owner.headers)).json()
    bank = (await factories.sql("SELECT id FROM ledgers WHERE org_id = :o AND system_code = 'CASH'", o=owner.org_id))[
        0
    ][0]
    r = await client.post(f"{P}/runs/{run['id']}/mark-paid", json={"bank_ledger_id": str(bank),
                                                                  "payment_date": "2026-10-01"}, headers=owner.headers)  # fmt: skip
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "PAID" and r.json()["payment_voucher_id"]
    pay = fakes.vouchers[-1]
    assert pay["base_type"] == "PAYMENT"
    assert [(str(e.ledger_id), e.entry_type, e.amount) for e in pay["entries"]] == [
        (s["salary_payable_ledger_id"], "DR", D(run["total_net_pay"])),
        (str(bank), "CR", D(run["total_net_pay"])),
    ]
    r = await client.post(f"{P}/runs/{run['id']}/mark-paid", json={"bank_ledger_id": str(bank),
                                                                  "payment_date": "2026-10-01"}, headers=owner.headers)  # fmt: skip
    assert r.status_code == 409


async def test_draft_bank_file_rejected(client, owner):
    await create_emp(client, owner)
    run = (await client.post(f"{P}/runs", json={"month": MONTH}, headers=owner.headers)).json()
    assert (await client.get(f"{P}/runs/{run['id']}/bank-file", headers=owner.headers)).status_code == 409
    r = await client.get(f"{P}/runs/{run['id']}/payslips/{run['lines'][0]['id']}", headers=owner.headers)
    assert r.status_code == 200 and r.content[:4] == b"%PDF"  # regenerated on demand


# ----------------------------------------------------------------- real interfaces (S2/S4)
async def test_lock_with_real_interfaces(client, owner):
    e = await create_emp(client, owner)
    await finalize(client, owner, [row(e)])
    run = (await client.post(f"{P}/runs", json={"month": MONTH}, headers=owner.headers)).json()
    r = await client.post(f"{P}/runs/{run['id']}/lock", headers=owner.headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "LOCKED_POSTED" and body["posted_voucher_id"]
    totals = await factories.sql(
        "SELECT entry_type, SUM(amount) FROM voucher_entries WHERE voucher_id = :v GROUP BY entry_type",
        v=uuid.UUID(body["posted_voucher_id"]),
    )
    sums = dict(totals)
    assert sums["DR"] == sums["CR"] == D(body["total_gross"]) + D(body["total_employer_contrib"])
    assert body["lines"][0]["payslip_document_id"]
