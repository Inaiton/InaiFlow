"""Operations API: workflows, runs lifecycle, step execution/routing, QC rules, locking, money flow."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from app.modules.operations.tests.helpers import (
    OD,
    edge,
    execute,
    get_run,
    new_run,
    node,
    published_workflow,
    simple_graph,
    step,
    stock_item,
)
from tests.factories import API, add_member, sql


async def _vouchers(run_id: str, base_type: str) -> int:
    rows = await sql("SELECT count(*) FROM vouchers v JOIN voucher_types t ON t.id = v.voucher_type_id "
                     "WHERE v.linked_period_run_id = :r AND t.base_type = :b", r=run_id, b=base_type)  # fmt: skip
    return rows[0][0]


# ---------------------------------------------------------------- workflows
async def test_workflow_publish_and_version_immutability(client, owner):
    r = await client.post(f"{API}/operations/workflows", headers=owner.headers,
                          json={"name": "CNC", "from_library_key": "cnc-machining-final-inspection"})  # fmt: skip
    assert r.status_code == 201, r.text
    wf = r.json()
    assert wf["status"] == "DRAFT" and wf["version"] == 1 and wf["node_count"] == 7 and wf["iso_clause_ref"] == "8.5.1"
    r = await client.put(f"{API}/operations/workflows/{wf['id']}", headers=owner.headers, json={"name": "CNC v1"})
    assert r.status_code == 200 and r.json()["name"] == "CNC v1"
    r = await client.post(f"{API}/operations/workflows/{wf['id']}/validate", headers=owner.headers)
    assert r.json()["valid"] is True
    assert (
        await client.post(f"{API}/operations/workflows/{wf['id']}/publish", headers=owner.headers)
    ).status_code == 200
    r = await client.put(f"{API}/operations/workflows/{wf['id']}", headers=owner.headers, json={"name": "x"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "WORKFLOW_PUBLISHED"
    r = await client.delete(f"{API}/operations/workflows/{wf['id']}", headers=owner.headers)
    assert r.json()["error"]["code"] == "WORKFLOW_PUBLISHED"
    r = await client.post(f"{API}/operations/workflows/{wf['id']}/new-version", headers=owner.headers)
    assert r.status_code == 201
    v2 = r.json()
    assert v2["version"] == 2 and v2["status"] == "DRAFT" and v2["template_key"] == wf["template_key"]
    assert v2["graph_definition"] == wf["graph_definition"]
    r = await client.post(f"{API}/operations/workflows/{wf['id']}/new-version", headers=owner.headers)
    assert r.status_code == 409
    r = await client.get(f"{API}/operations/workflows/{v2['id']}/versions", headers=owner.headers)
    assert [v["version"] for v in r.json()] == [2, 1]
    listed = (await client.get(f"{API}/operations/workflows", headers=owner.headers)).json()
    assert [w["version"] for w in listed if w["template_key"] == wf["template_key"]] == [2]
    every = (await client.get(f"{API}/operations/workflows?all_versions=true", headers=owner.headers)).json()
    assert len([w for w in every if w["template_key"] == wf["template_key"]]) == 2
    assert (await client.delete(f"{API}/operations/workflows/{v2['id']}", headers=owner.headers)).status_code == 204


async def test_invalid_graph_cannot_publish(client, owner):
    graph = {"nodes": [node("a", "RECTANGLE", "A")], "edges": [edge("a", "ghost")]}
    r = await client.post(
        f"{API}/operations/workflows", headers=owner.headers, json={"name": "bad", "graph_definition": graph}
    )
    wid = r.json()["id"]
    res = (await client.post(f"{API}/operations/workflows/{wid}/validate", headers=owner.headers)).json()
    assert res["valid"] is False and res["errors"]
    r = await client.post(f"{API}/operations/workflows/{wid}/publish", headers=owner.headers)
    assert r.status_code == 400 and r.json()["error"]["code"] == "WORKFLOW_INVALID"


async def test_library_and_draft_run_rejected(client, owner):
    lib = (await client.get(f"{API}/operations/workflow-library", headers=owner.headers)).json()
    assert {t["key"] for t in lib} >= {"incoming-material-inspection", "assembly-and-test"}
    r = await client.post(
        f"{API}/operations/workflows", headers=owner.headers, json={"name": "d", "graph_definition": simple_graph()}
    )
    r = await client.post(f"{API}/operations/runs", headers=owner.headers,
                          json={"workflow_id": r.json()["id"], "period_month": "2026-09-01", "planned_qty": "5"})  # fmt: skip
    assert r.status_code == 409


# ---------------------------------------------------------------- run lifecycle
async def test_full_run_lifecycle_with_reject_rework_skip_and_succeed(client, owner):
    item = await stock_item(owner.org_id, rate="10")
    wf = await published_workflow(client, owner)
    run = await new_run(client, owner, wf, "100", stock_item_id=str(item))
    assert run["status"] == "IN_PROGRESS" and run["workflow_version"] == 1
    assert [s["node_id"] for s in run["steps"]] == ["start", "cut", "qc", "end"]
    assert [s["sequence"] for s in run["steps"]] == [1, 2, 3, 4]
    assert step(run, "start")["status"] == "ACTIVE" and step(run, "start")["input_qty"] == "100.00"
    assert run["cost_centre_id"] and run["doc_folder_id"]
    folder = (await sql("SELECT name, is_system_locked, linked_period_run_id FROM doc_folders WHERE id = :i",
                        i=run["doc_folder_id"]))[0]  # fmt: skip
    assert folder.name == run["run_title"] and folder.is_system_locked

    r = await execute(client, owner, run, "start", input_qty="100", accepted_qty="100", rejected_qty="0")
    assert r.status_code == 200, r.text
    assert r.json()["step"]["status"] == "PASSED" and len(r.json()["activated_step_ids"]) == 1
    run = await get_run(client, owner, run)
    sid = step(run, "cut")["id"]
    r = await client.post(
        f"{API}/operations/runs/{run['id']}/steps/{sid}/skip", headers=owner.headers, json={"reason": "Pre-cut stock"}
    )
    assert r.status_code == 200 and r.json()["step"]["status"] == "SKIPPED" and r.json()["step"]["skip_reason"]

    r = await execute(client, owner, run, "qc", input_qty="100", accepted_qty="90", rejected_qty="8", rework_qty="2",
                      measurements={"od": "25.01"}, defect_description="Oversize OD")  # fmt: skip
    assert r.status_code == 200, r.text
    out = r.json()
    year = date.today().year
    assert out["ncr"]["ncr_number"] == f"NCR-{year}-0001" and out["ncr"]["source"] == "AUTO_QC"
    assert out["ncr"]["status"] == "OPEN" and out["ncr"]["rejected_qty"] == "8.00"
    assert out["stock_voucher_id"]
    assert out["step"]["qc_measurements"]["od"] == {"value": "25.01", "in_tolerance": True, "auto_filled": False}
    assert await _vouchers(run["id"], "STOCK_JOURNAL") == 1
    run = await get_run(client, owner, run)
    assert step(run, "cut")["status"] == "ACTIVE" and step(run, "cut")["input_qty"] == "102.00"
    assert step(run, "qc")["status"] == "PASSED"  # rework sent upstream; it comes back as new input
    assert step(run, "end")["input_qty"] == "90.00" and run["rejected_qty"] == "8.00" and run["rework_qty"] == "2.00"

    r = await execute(client, owner, run, "cut", input_qty="2", accepted_qty="2", rejected_qty="0")
    assert r.status_code == 200, r.text
    run = await get_run(client, owner, run)
    sid = step(run, "qc")["id"]
    r = await client.post(
        f"{API}/operations/runs/{run['id']}/steps/{sid}/succeed",
        headers=owner.headers,
        json={"reason": "Re-machined OK"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["step"]["status"] == "PASSED" and r.json()["step"]["quick_qc"] is True

    r = await client.post(f"{API}/operations/runs/{run['id']}/complete", headers=owner.headers)
    assert r.status_code == 409 and "open_steps" in r.json()["error"]["details"]
    r = await execute(client, owner, run, "end", input_qty="92", accepted_qty="92", rejected_qty="0")
    assert r.status_code == 200 and r.json()["run"]["accepted_qty"] == "92.00"
    assert await _vouchers(run["id"], "STOCK_JOURNAL") == 2

    ledgers = await sql("SELECT system_code, id FROM ledgers WHERE org_id = :o AND system_code IN ('MFG_OVERHEAD','CASH')",
                        o=owner.org_id)  # fmt: skip
    lid = dict((c, str(i)) for c, i in ledgers)
    r = await client.post(f"{API}/operations/runs/{run['id']}/postings", headers=owner.headers,
                          json={"entry_type": "DR", "amount": "1012", "ledger_id": lid["MFG_OVERHEAD"],
                                "contra_ledger_id": lid["CASH"], "voucher_date": "2026-09-15"})  # fmt: skip
    assert r.status_code == 201, r.text
    mf = r.json()["money_flow"]
    assert mf["total_debit"] == "1012.00" and mf["unit_cost"] == "11.00" and mf["debits"][0]["source"] == "POSTING"
    r = await client.post(f"{API}/operations/runs/{run['id']}/postings", headers=owner.headers,
                          json={"entry_type": "CR", "amount": "92", "ledger_id": lid["MFG_OVERHEAD"],
                                "contra_ledger_id": lid["CASH"], "voucher_date": "2026-09-15"})  # fmt: skip
    assert r.json()["money_flow"]["net_cost"] == "920.00" and r.json()["money_flow"]["unit_cost"] == "10.00"

    r = await client.post(f"{API}/operations/runs/{run['id']}/complete", headers=owner.headers)
    assert r.status_code == 200, r.text
    done = r.json()
    assert done["status"] == "COMPLETED" and done["computed_unit_cost"] == "10.00" and done["completed_at"]
    assert done["progress_pct"] == "100.00" and done["yield_pct"] == "92.00"
    assert await _vouchers(run["id"], "MFG_JOURNAL") == 1
    ncrs = (await client.get(f"{API}/operations/ncr?period_run_id={run['id']}", headers=owner.headers)).json()
    assert ncrs["total"] == 1
    r = await execute(client, owner, run, "end", input_qty="1", accepted_qty="1", rejected_qty="0")
    assert r.status_code == 409  # run completed


async def test_execution_validations(client, owner):
    wf = await published_workflow(client, owner)
    run = await new_run(client, owner, wf, "10")
    r = await execute(client, owner, run, "qc", input_qty="1", accepted_qty="1", rejected_qty="0")
    assert r.status_code == 409 and r.json()["error"]["code"] == "STEP_NOT_ACTIVE"
    r = await execute(client, owner, run, "start", input_qty="10", accepted_qty="8", rejected_qty="1")
    assert r.status_code == 400 and r.json()["error"]["code"] == "QTY_MISMATCH"
    r = await execute(client, owner, run, "start", input_qty="11", accepted_qty="11", rejected_qty="0")
    assert r.json()["error"]["code"] == "QTY_MISMATCH"
    r = await execute(client, owner, run, "start", input_qty="4", accepted_qty="4", rejected_qty="0")
    assert r.status_code == 200 and r.json()["step"]["status"] == "ACTIVE"  # partial batch, 6 pending
    await execute(client, owner, run, "start", input_qty="6", accepted_qty="6", rejected_qty="0")
    run = await get_run(client, owner, run)
    await client.post(
        f"{API}/operations/runs/{run['id']}/steps/{step(run, 'cut')['id']}/succeed", headers=owner.headers, json={}
    )
    r = await execute(
        client, owner, run, "qc", input_qty="10", accepted_qty="10", rejected_qty="0", measurements={"od": "25.5"}
    )
    assert r.status_code == 400 and r.json()["error"]["details"]["criteria"] == "FAILED"
    r = await execute(
        client, owner, run, "qc", input_qty="10", accepted_qty="10", rejected_qty="0", measurements={"od": "abc"}
    )
    assert r.status_code == 400 and r.json()["error"]["details"]["field"] == "od"
    r = await execute(
        client, owner, run, "qc", input_qty="10", accepted_qty="0", rejected_qty="10", measurements={"od": "25.5"}
    )
    assert r.status_code == 200 and r.json()["step"]["status"] == "REJECTED" and r.json()["ncr"]
    r = await execute(client, owner, run, "end", input_qty="1", accepted_qty="1", rejected_qty="0")
    assert r.json()["error"]["code"] == "STEP_NOT_ACTIVE"
    r = await client.post(f"{API}/operations/runs/{run['id']}/complete", headers=owner.headers)
    assert r.status_code == 200 and r.json()["accepted_qty"] == "0.00"  # everything scrapped, still closable


async def test_quick_qc_autofills_nominal(client, owner):
    wf = await published_workflow(client, owner)
    run = await new_run(client, owner, wf, "5")
    await execute(client, owner, run, "start", input_qty="5", accepted_qty="5", rejected_qty="0")
    await execute(client, owner, run, "cut", input_qty="5", accepted_qty="5", rejected_qty="0")
    r = await execute(client, owner, run, "qc", input_qty="5", accepted_qty="5", rejected_qty="0", quick_qc=True)
    assert r.status_code == 200, r.text
    s = r.json()["step"]
    assert s["quick_qc"] is True
    assert s["qc_measurements"]["od"] == {"value": "25.00", "in_tolerance": True, "auto_filled": True}


async def test_omitted_measurement_autofills_without_flag(client, owner):
    graph = simple_graph()
    graph["nodes"][2]["config"]["qc_fields"] = [OD, {**OD, "key": "len", "label": "Length", "nominal": "100"}]
    wf = await published_workflow(client, owner, graph)
    run = await new_run(client, owner, wf, "1")
    await execute(client, owner, run, "start", input_qty="1", accepted_qty="1", rejected_qty="0")
    await execute(client, owner, run, "cut", input_qty="1", accepted_qty="1", rejected_qty="0")
    r = await execute(
        client, owner, run, "qc", input_qty="1", accepted_qty="1", rejected_qty="0", measurements={"od": "25.01"}
    )
    readings = r.json()["step"]["qc_measurements"]
    assert readings["od"]["auto_filled"] is False and readings["len"]["auto_filled"] is True
    assert r.json()["step"]["quick_qc"] is True


async def test_locked_step_requires_override(client, owner):
    operator = await add_member(owner.org_id, "OPERATOR")
    qa = await add_member(owner.org_id, "QA_LEAD")
    wf = await published_workflow(client, owner)
    run = await new_run(client, owner, wf, "10")
    sid = step(run, "start")["id"]
    r = await client.post(f"{API}/operations/runs/{run['id']}/steps/{sid}/signoff", headers=operator.headers)
    assert r.status_code == 403
    r = await client.post(f"{API}/operations/runs/{run['id']}/steps/{sid}/signoff", headers=qa.headers)
    assert r.status_code == 200 and r.json()["is_locked"] is True and r.json()["signed_off_by_name"]
    r = await execute(client, operator, run, "start", input_qty="10", accepted_qty="10", rejected_qty="0")
    assert r.status_code == 423 and r.json()["error"]["code"] == "STEP_LOCKED"
    r = await execute(client, qa, run, "start", input_qty="10", accepted_qty="10", rejected_qty="0")
    assert r.status_code == 423  # FULL but no reason
    r = await execute(client, qa, run, "start", input_qty="10", accepted_qty="10", rejected_qty="0",
                      override_reason="Count corrected after sign-off")  # fmt: skip
    assert r.status_code == 200 and r.json()["step"]["override_reason"]
    rows = await sql("SELECT action, reason FROM org_audit_logs WHERE entity_id = :i AND action = 'OVERRIDE'", i=sid)
    assert rows and rows[0].reason == "Count corrected after sign-off"
    r = await client.post(
        f"{API}/operations/runs/{run['id']}/steps/{sid}/reopen", headers=operator.headers, json={"reason": "x"}
    )
    assert r.status_code == 403
    r = await client.post(
        f"{API}/operations/runs/{run['id']}/steps/{sid}/reopen", headers=qa.headers, json={"reason": "Re-inspect"}
    )
    assert r.status_code == 200 and r.json()["is_locked"] is False


async def test_expired_instrument_blocks_execution(client, owner):
    past = date.today() - timedelta(days=3)
    r = await client.post(f"{API}/operations/instruments", headers=owner.headers,
                          json={"instrument_code": "VC-01", "name": "Vernier", "last_calibrated_date": str(past - timedelta(days=365)),
                                "next_due_date": str(past)})  # fmt: skip
    assert r.status_code == 201 and r.json()["status"] == "EXPIRED" and r.json()["days_to_due"] == -3
    inst = r.json()["id"]
    wf = await published_workflow(client, owner)
    run = await new_run(client, owner, wf, "1")
    r = await execute(
        client, owner, run, "start", input_qty="1", accepted_qty="1", rejected_qty="0", instrument_id=inst
    )
    assert r.status_code == 423 and r.json()["error"]["code"] == "INSTRUMENT_EXPIRED"
    r = await client.post(f"{API}/operations/instruments/{inst}/calibrate", headers=owner.headers,
                          json={"calibrated_on": str(date.today()), "next_due_date": str(date.today() + timedelta(days=20))})  # fmt: skip
    assert r.json()["status"] == "DUE_SOON"
    r = await execute(
        client, owner, run, "start", input_qty="1", accepted_qty="1", rejected_qty="0", instrument_id=inst
    )
    assert r.status_code == 200 and r.json()["step"]["instrument_id"] == inst


async def test_operator_can_execute_but_not_publish(client, owner):
    operator = await add_member(owner.org_id, "OPERATOR")
    r = await client.post(
        f"{API}/operations/workflows", headers=operator.headers, json={"name": "x", "graph_definition": simple_graph()}
    )
    assert r.status_code == 403
    r = await client.post(
        f"{API}/operations/workflows", headers=owner.headers, json={"name": "y", "graph_definition": simple_graph()}
    )
    r = await client.post(f"{API}/operations/workflows/{r.json()['id']}/publish", headers=operator.headers)
    assert r.status_code == 403
    wf = await published_workflow(client, owner)
    run = await new_run(client, operator, wf, "3")
    r = await execute(client, operator, run, "start", input_qty="3", accepted_qty="3", rejected_qty="0")
    assert r.status_code == 200
    r = await client.post(f"{API}/operations/runs/{run['id']}/cancel", headers=operator.headers, json={"reason": "x"})
    assert r.status_code == 403  # FULL needed


async def test_run_state_machine(client, owner):
    wf = await published_workflow(client, owner)
    run = await new_run(client, owner, wf, "5", start_now=False)
    assert run["status"] == "PLANNED" and all(s["status"] == "PENDING" for s in run["steps"])
    r = await execute(client, owner, run, "start", input_qty="5", accepted_qty="5", rejected_qty="0")
    assert r.status_code == 409
    rid = run["id"]
    r = await client.post(f"{API}/operations/runs/{rid}/start", headers=owner.headers)
    assert r.json()["status"] == "IN_PROGRESS" and step(r.json(), "start")["status"] == "ACTIVE"
    r = await client.post(f"{API}/operations/runs/{rid}/hold", headers=owner.headers, json={"reason": "Gauge check"})
    assert r.json()["status"] == "QC_HOLD" and r.json()["hold_reason"] == "Gauge check"
    r = await execute(client, owner, run, "start", input_qty="5", accepted_qty="5", rejected_qty="0")
    assert r.json()["error"]["code"] == "INVALID_STATE"
    assert (
        await client.post(f"{API}/operations/runs/{rid}/hold", headers=owner.headers, json={"reason": "x"})
    ).status_code == 409
    assert (await client.post(f"{API}/operations/runs/{rid}/resume", headers=owner.headers)).json()[
        "status"
    ] == "IN_PROGRESS"
    r = await client.post(
        f"{API}/operations/runs/{rid}/cancel", headers=owner.headers, json={"reason": "Order cancelled"}
    )
    assert r.json()["status"] == "CANCELLED" and r.json()["cancel_reason"] == "Order cancelled"
    listed = (await client.get(f"{API}/operations/runs?status=CANCELLED", headers=owner.headers)).json()
    assert rid in [x["id"] for x in listed["items"]]


async def test_cross_tenant_run_is_404(client, owner):
    from tests.factories import org_with_owner

    other = await org_with_owner(client)
    wf = await published_workflow(client, owner)
    run = await new_run(client, owner, wf, "1")
    assert (await client.get(f"{API}/operations/runs/{run['id']}", headers=other.headers)).status_code == 404
    assert (await client.get(f"{API}/operations/workflows/{wf['id']}", headers=other.headers)).status_code == 404


async def test_link_and_unlink_voucher(client, owner):
    wf = await published_workflow(client, owner)
    run = await new_run(client, owner, wf, "10")
    vt = (
        await sql("SELECT id FROM voucher_types WHERE org_id = :o AND base_type = 'PURCHASE' LIMIT 1", o=owner.org_id)
    )[0][0]
    vid = (await sql("INSERT INTO vouchers (org_id, voucher_type_id, voucher_number, voucher_date, total_amount, created_by) "
                     "VALUES (:o, :t, 'PUR-1', '2026-09-03', 500, :u) RETURNING id", o=owner.org_id, t=vt,
                     u=owner.user_id))[0][0]  # fmt: skip
    r = await client.post(f"{API}/operations/runs/{run['id']}/linked-vouchers", headers=owner.headers,
                          json={"voucher_id": str(vid), "step_id": step(run, "cut")["id"]})  # fmt: skip
    assert r.status_code == 200, r.text
    assert r.json()["total_debit"] == "500.00" and r.json()["debits"][0]["voucher_number"] == "PUR-1"
    assert r.json()["debits"][0]["step_id"] == step(run, "cut")["id"]
    r = await client.delete(f"{API}/operations/runs/{run['id']}/linked-vouchers/{vid}", headers=owner.headers)
    assert r.status_code == 204
    mf = (await client.get(f"{API}/operations/runs/{run['id']}/money-flow", headers=owner.headers)).json()
    assert mf["total_debit"] == "0.00"
    r = await client.delete(f"{API}/operations/runs/{run['id']}/linked-vouchers/{vid}", headers=owner.headers)
    assert r.status_code == 404


async def test_interface_payroll_allocation_and_queries(client, owner):
    from app.core.context import TenantContext
    from app.core.db import get_sessionmaker, set_tenant_scope
    from app.modules.operations import interface as ops

    wf = await published_workflow(client, owner)
    run = await new_run(client, owner, wf, "10")
    await execute(client, owner, run, "start", input_qty="10", accepted_qty="10", rejected_qty="0")
    ctx = TenantContext.system(owner.org_id, user_id=owner.user_id)
    import uuid as _uuid
    from decimal import Decimal

    rid = _uuid.UUID(run["id"])
    async with get_sessionmaker()() as s, s.begin():
        await set_tenant_scope(s, owner.org_id, owner.user_id)
        await ops.apply_payroll_allocation(s, ctx, rid, Decimal("2500"))
        briefs = await ops.get_runs_by_ids(s, ctx, [rid])
        execs = await ops.list_step_executions_by_month(s, ctx, date.today())
        costing = await ops.list_runs_for_costing(s, ctx, date(2026, 9, 1), date(2026, 9, 30))
    assert briefs[0].total_debit_cost == Decimal("2500")
    assert any(e.period_run_id == rid and e.accepted_qty == 10 for e in execs)
    assert rid in [c.id for c in costing]
    mf = (await client.get(f"{API}/operations/runs/{run['id']}/money-flow", headers=owner.headers)).json()
    assert mf["debits"][0]["source"] == "PAYROLL" and mf["total_debit"] == "2500.00"


async def test_dossier_pdf_docx_and_save(client, owner):
    item = await stock_item(owner.org_id)
    wf = await published_workflow(client, owner)
    run = await new_run(client, owner, wf, "4", stock_item_id=str(item))
    await execute(client, owner, run, "start", input_qty="4", accepted_qty="4", rejected_qty="0")
    r = await client.get(f"{API}/operations/runs/{run['id']}/dossier?format=pdf", headers=owner.headers)
    assert r.status_code == 200 and r.content[:4] == b"%PDF" and r.headers["content-type"] == "application/pdf"
    r = await client.get(f"{API}/operations/runs/{run['id']}/dossier?format=docx&save=true", headers=owner.headers)
    assert r.status_code == 200 and r.content[:2] == b"PK"
    docs = await sql("SELECT title, folder_id FROM documents WHERE linked_period_run_id = :r", r=run["id"])
    assert docs and str(docs[0].folder_id) == run["doc_folder_id"]
    assert (
        await client.get(f"{API}/operations/runs/{run['id']}/dossier?format=xls", headers=owner.headers)
    ).status_code == 400


async def test_auditor_sees_only_granted_item_runs(client, owner):
    from tests.factories import create_user

    item_a, item_b = await stock_item(owner.org_id, "Component A"), await stock_item(owner.org_id, "Component B")
    wf = await published_workflow(client, owner)
    run_a = await new_run(client, owner, wf, "1", stock_item_id=str(item_a))
    run_b = await new_run(client, owner, wf, "1", stock_item_id=str(item_b))
    auditor = await create_user(mfa=True, full_name="Isha Auditor")
    expires = (datetime.now(UTC) + timedelta(days=10)).isoformat()
    r = await client.post(f"{API}/operations/iso/auditor-invites", headers=owner.headers,
                          json={"email": auditor.email, "access_expires_at": expires, "stock_item_ids": [str(item_a)]})  # fmt: skip
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "PENDING" and r.json()["role_name"]
    r = await client.post(f"{API}/me/invitations/{r.json()['id']}/accept", headers=auditor.user_headers)
    assert r.status_code == 200, r.text
    aud = auditor.in_org(owner.org_id)
    listed = (await client.get(f"{API}/operations/runs", headers=aud.headers)).json()
    assert [x["id"] for x in listed["items"]] == [run_a["id"]]
    assert (await client.get(f"{API}/operations/runs/{run_a['id']}", headers=aud.headers)).status_code == 200
    assert (await client.get(f"{API}/operations/runs/{run_b['id']}", headers=aud.headers)).status_code == 404
    r = await execute(client, owner, run_a, "start", input_qty="1", accepted_qty="1", rejected_qty="0")
    sid = step(run_a, "cut")["id"]
    r = await client.post(f"{API}/operations/runs/{run_a['id']}/steps/{sid}/succeed", headers=aud.headers, json={})
    assert r.status_code == 403  # READ only
    assert (await client.get(f"{API}/operations/items/{item_b}/runs", headers=aud.headers)).status_code == 404
    r = await client.post(f"{API}/operations/iso/auditor-invites", headers=owner.headers,
                          json={"email": "x@example.com", "access_expires_at": "2020-01-01T00:00:00Z"})  # fmt: skip
    assert r.status_code == 400


async def test_ncr_checklist_readiness_dashboard(client, owner):
    r = await client.post(f"{API}/operations/ncr", headers=owner.headers,
                          json={"rejected_qty": "3", "defect_description": "Burr on edge"})  # fmt: skip
    assert r.status_code == 201 and r.json()["source"] == "MANUAL"
    nid = r.json()["id"]
    r = await client.patch(f"{API}/operations/ncr/{nid}", headers=owner.headers,
                           json={"root_cause_analysis": "Worn tool", "status": "IN_PROGRESS"})  # fmt: skip
    assert r.json()["status"] == "IN_PROGRESS" and r.json()["root_cause_analysis"] == "Worn tool"
    assert (
        await client.patch(f"{API}/operations/ncr/{nid}", headers=owner.headers, json={"status": "CLOSED"})
    ).status_code == 400
    qa = await add_member(owner.org_id, "OPERATOR")
    assert (
        await client.post(f"{API}/operations/ncr/{nid}/close", headers=qa.headers, json={"verification_notes": "x"})
    ).status_code == 403
    r = await client.post(
        f"{API}/operations/ncr/{nid}/close", headers=owner.headers, json={"verification_notes": "Tool replaced"}
    )
    assert r.json()["status"] == "CLOSED" and r.json()["closed_by_name"]
    assert (
        await client.post(f"{API}/operations/ncr/{nid}/close", headers=owner.headers, json={"verification_notes": "x"})
    ).status_code == 409
    items = (await client.get(f"{API}/operations/iso/checklist", headers=owner.headers)).json()
    assert len(items) >= 10
    r = await client.patch(
        f"{API}/operations/iso/checklist/{items[0]['id']}", headers=owner.headers, json={"status": "COMPLIANT"}
    )
    assert r.json()["status"] == "COMPLIANT" and r.json()["updated_by_name"]
    assert (await client.patch(f"{API}/operations/iso/checklist/{items[0]['id']}", headers=owner.headers,
                               json={"status": "DONE"})).status_code == 400  # fmt: skip
    ready = (await client.get(f"{API}/operations/iso/readiness", headers=owner.headers)).json()
    assert ready["by_clause"][0]["clause"] == "4" and ready["by_clause"][0]["compliant"] == 1
    assert 0 < float(ready["score_pct"]) < 100
    dash = await client.get(f"{API}/operations/dashboard", headers=owner.headers)
    assert dash.status_code == 200 and len(dash.json()["yield_series"]) == 6
    assert {k["key"] for k in dash.json()["kpis"]} >= {"active_runs", "open_ncrs"}


async def test_items_facade_lists_stock_items(client, owner):
    item = await stock_item(owner.org_id, "Facade Item")
    wf = await published_workflow(client, owner, stock_item_id=str(item))
    await new_run(client, owner, wf, "2")
    r = await client.get(f"{API}/operations/items/{item}", headers=owner.headers)
    assert r.status_code == 200 and r.json()["stats"]["run_count"] == 1 and r.json()["workflow_count"] == 1
    listed = (await client.get(f"{API}/operations/items?q=Facade", headers=owner.headers)).json()
    assert [i["id"] for i in listed["items"]] == [str(item)]
