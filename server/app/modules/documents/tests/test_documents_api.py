"""Documents API: folder rules, uploads (LocalStorage), template rendering, ISO approval chain, ACL."""

from __future__ import annotations

from urllib.parse import urlsplit

from tests.factories import API, add_member, sql, unique

# Minimal operations helpers (module tests may not import another module's private packages).
OD = {"key": "od", "label": "OD", "type": "NUMBER", "nominal": "25.00", "tol_minus": "0.02", "tol_plus": "0.02"}
GRAPH = {
    "nodes": [{"id": i, "shape": sh, "label": i.upper(), "position": {"x": "0", "y": "0"}, "config": cfg}
              for i, sh, cfg in (("start", "OVAL", {}), ("cut", "RECTANGLE", {}),
                                 ("qc", "DIAMOND", {"qc_fields": [OD], "pass_criteria": {"mode": "ALL_FIELDS_IN_TOLERANCE"}}),
                                 ("end", "TERMINATOR", {}))],
    "edges": [{"id": f"{s}-{t}", "source": s, "target": t, "branch": "PASS"}
              for s, t in (("start", "cut"), ("cut", "qc"), ("qc", "end"))],
}  # fmt: skip


def step(run: dict, node_id: str) -> dict:
    return next(s for s in run["steps"] if s["node_id"] == node_id)


async def published_workflow(client, actor):  # noqa: ANN001,ANN201
    r = await client.post(
        f"{API}/operations/workflows", headers=actor.headers, json={"name": unique("WF"), "graph_definition": GRAPH}
    )
    return (await client.post(f"{API}/operations/workflows/{r.json()['id']}/publish", headers=actor.headers)).json()


async def new_run(client, actor, wf, qty):  # noqa: ANN001,ANN201
    body = {"workflow_id": wf["id"], "period_month": "2026-09-01", "planned_qty": qty, "run_title": unique("Run ")}
    return (await client.post(f"{API}/operations/runs", headers=actor.headers, json=body)).json()


async def execute(client, actor, run, node_id, **body):  # noqa: ANN001,ANN003,ANN201
    sid = step(run, node_id)["id"]
    return await client.post(f"{API}/operations/runs/{run['id']}/steps/{sid}/execute", headers=actor.headers, json=body)


async def _folders(client, actor, parent=None):  # noqa: ANN001,ANN202
    q = f"?parent_id={parent}" if parent else ""
    r = await client.get(f"{API}/documents/folders{q}", headers=actor.headers)
    assert r.status_code == 200, r.text
    return r.json()


async def _month(client, owner):  # noqa: ANN001,ANN202
    r = await client.post(f"{API}/documents/folders/ensure-month", headers=owner.headers, json={"month": "2026-09-01"})
    assert r.status_code == 200, r.text
    return r.json()


def _rel(url: str) -> str:
    parts = urlsplit(url)
    return parts.path + (f"?{parts.query}" if parts.query else "")


async def _upload(client, actor, folder_id, data=b"%PDF-1.4 test", name="bill.pdf", **extra):  # noqa: ANN001,ANN202
    r = await client.post(f"{API}/documents/upload-url", headers=actor.headers,
                          json={"folder_id": folder_id, "title": extra.pop("title", "Supplier bill"), "file_name": name,
                                "content_type": "application/pdf", "size_bytes": len(data), **extra})  # fmt: skip
    assert r.status_code == 201, r.text
    ticket = r.json()["upload"]
    put = await client.request(ticket["method"], _rel(ticket["upload_url"]), content=data, headers=ticket["headers"])
    assert put.status_code in (200, 204), put.text
    r2 = await client.post(
        f"{API}/documents/{r.json()['document']['id']}/complete-upload", headers=actor.headers, json={}
    )
    assert r2.status_code == 200, r2.text
    return r2.json()


async def test_folder_rules(client, owner):
    roots = await _folders(client, owner)
    assert {"FY_ROOT", "MASTER_LIBRARY"} <= {f["system_kind"] for f in roots}
    tree = await _month(client, owner)
    month, subs = tree[0], tree[1:]
    assert month["name"] == "09 - September 2026" and month["is_system_locked"] and len(subs) == 3
    r = await client.patch(f"{API}/documents/folders/{month['id']}", headers=owner.headers, json={"name": "x"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "FOLDER_LOCKED"
    assert (await client.delete(f"{API}/documents/folders/{month['id']}", headers=owner.headers)).json()["error"][
        "code"
    ] == "FOLDER_LOCKED"
    r = await client.post(
        f"{API}/documents/folders", headers=owner.headers, json={"parent_folder_id": month["id"], "name": "QC Logs"}
    )
    assert r.status_code == 201 and r.json()["fy_label"] == month["fy_label"]
    qc = r.json()
    r = await client.post(
        f"{API}/documents/folders", headers=owner.headers, json={"parent_folder_id": month["id"], "name": "qc logs"}
    )
    assert r.status_code == 409
    assert (await client.post(f"{API}/documents/folders", headers=owner.headers,
                              json={"parent_folder_id": month["id"], "name": "a/b"})).status_code == 400  # fmt: skip
    child = (await client.post(f"{API}/documents/folders", headers=owner.headers,
                               json={"parent_folder_id": qc["id"], "name": "Shift A"})).json()  # fmt: skip
    r = await client.patch(
        f"{API}/documents/folders/{qc['id']}", headers=owner.headers, json={"parent_folder_id": child["id"]}
    )
    assert r.status_code == 409 and r.json()["error"]["code"] == "CONFLICT"
    r = await client.delete(f"{API}/documents/folders/{qc['id']}", headers=owner.headers)
    assert r.json()["error"]["code"] == "FOLDER_NOT_EMPTY"
    path = (await client.get(f"{API}/documents/folders/{child['id']}/path", headers=owner.headers)).json()
    assert [p["name"] for p in path][-3:] == ["09 - September 2026", "QC Logs", "Shift A"]
    assert (await client.delete(f"{API}/documents/folders/{child['id']}", headers=owner.headers)).status_code == 204
    r = await client.patch(f"{API}/documents/folders/{qc['id']}", headers=owner.headers, json={"name": "QC Logs 2"})
    assert r.json()["name"] == "QC Logs 2"


async def test_custom_monthly_folder_rule(client, owner):
    r = await client.post(f"{API}/documents/templates", headers=owner.headers,
                          json={"template_type": "MONTHLY_FOLDER_RULE", "name": "Extra", "content_schema": {"custom": ["Customer POs"]}})  # fmt: skip
    assert r.status_code == 201, r.text
    tree = await _month(client, owner)
    assert "Customer POs" in [f["name"] for f in tree]
    accountant = await add_member(owner.org_id, "ACCOUNTANT")
    r = await client.post(
        f"{API}/documents/folders/ensure-month", headers=accountant.headers, json={"month": "2026-10-01"}
    )
    assert r.status_code == 403


async def test_upload_download_and_search(client, owner):
    bills = (await _month(client, owner))[1]
    r = await client.post(f"{API}/documents/upload-url", headers=owner.headers,
                          json={"folder_id": bills["id"], "title": "x", "file_name": "a.exe",
                                "content_type": "application/x-msdownload", "size_bytes": 10})  # fmt: skip
    assert r.status_code == 415
    r = await client.post(f"{API}/documents/upload-url", headers=owner.headers,
                          json={"folder_id": bills["id"], "title": "x", "file_name": "a.pdf",
                                "content_type": "application/pdf", "size_bytes": 60 * 1024 * 1024})  # fmt: skip
    assert r.status_code == 413
    r = await client.post(f"{API}/documents/upload-url", headers=owner.headers,
                          json={"folder_id": bills["id"], "title": "Pending", "file_name": "p.pdf",
                                "content_type": "application/pdf", "size_bytes": 5})  # fmt: skip
    pending = r.json()["document"]
    assert pending["upload_status"] == "PENDING"
    key = r.json()["upload"]["storage_key"]
    assert key.startswith(f"org/{owner.org_id}/") and key.endswith("/p.pdf")
    r = await client.post(f"{API}/documents/{pending['id']}/complete-upload", headers=owner.headers, json={})
    assert r.status_code == 409 and r.json()["error"]["code"] == "UPLOAD_INCOMPLETE"
    assert (await client.get(f"{API}/documents/{pending['id']}/download-url", headers=owner.headers)).status_code == 409

    doc = await _upload(client, owner, bills["id"], title="Steel invoice Tata")
    assert doc["upload_status"] == "READY" and doc["folder_path"][-1] == "Bills & Vouchers"
    r = await client.get(f"{API}/documents/{doc['id']}/download-url", headers=owner.headers)
    assert r.status_code == 200
    body = await client.get(_rel(r.json()["url"]))
    assert body.status_code == 200 and body.content == b"%PDF-1.4 test"
    hits = (await client.get(f"{API}/documents/search?q=steel", headers=owner.headers)).json()
    assert [h["document"]["id"] for h in hits] == [doc["id"]] and hits[0]["folder_path"]
    listed = (await client.get(f"{API}/documents?folder_id={bills['id']}", headers=owner.headers)).json()
    assert listed["total"] == 2
    assert (await client.delete(f"{API}/documents/{doc['id']}", headers=owner.headers)).status_code == 204


async def test_template_render_with_run_context(client, owner):
    wf = await published_workflow(client, owner)
    run = await new_run(client, owner, wf, "10")
    await execute(client, owner, run, "start", input_qty="10", accepted_qty="10", rejected_qty="0")
    await execute(client, owner, run, "cut", input_qty="10", accepted_qty="10", rejected_qty="0")
    r = await execute(
        client, owner, run, "qc", input_qty="10", accepted_qty="9", rejected_qty="1", measurements={"od": "25.01"}
    )
    assert r.status_code == 200
    tokens = (await client.get(f"{API}/documents/template-tokens", headers=owner.headers)).json()
    assert {"{{run.title}}", "{{step.qc_readings}}", "{{accounts.unit_cost}}"} <= {t["token"] for t in tokens}
    tpls = (await client.get(f"{API}/documents/templates?template_type=REPORT_DOC", headers=owner.headers)).json()
    ncr_tpl = next(t for t in tpls if t["name"] == "NCR / CAPA Form")
    fai = next(t for t in tpls if t["name"] == "First Article Inspection")
    ctx = {"period_run_id": run["id"], "step_id": step(run, "qc")["id"]}
    r = await client.post(
        f"{API}/documents/templates/{fai['id']}/preview", headers=owner.headers, json={"context": ctx}
    )
    assert r.status_code == 200, r.text
    blocks = r.json()["rich_content"]["blocks"]
    qc_block = next(b for b in blocks if b["type"] == "qc_table")
    assert qc_block["data"]["rows"][0][3] == "25.01" and "OK" in qc_block["data"]["rows"][0][4]
    kv = next(b for b in blocks if b["type"] == "kv")
    assert any(row["value"].startswith(run["run_title"]) for row in kv["data"]["rows"])
    run_folder = run["doc_folder_id"]
    r = await client.post(f"{API}/documents", headers=owner.headers,
                          json={"folder_id": run_folder, "title": "NCR form", "source_type": "INTERNAL_TEMPLATE",
                                "template_id": ncr_tpl["id"], "context": ctx})  # fmt: skip
    assert r.status_code == 201, r.text
    doc = r.json()
    text = str(doc["rich_content"])
    assert "NCR-" in text and "{{" not in text and doc["linked_step_id"] == ctx["step_id"]
    pdf = await client.get(f"{API}/documents/{doc['id']}/export?format=pdf", headers=owner.headers)
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"
    r = await client.delete(f"{API}/documents/{doc['id']}", headers=owner.headers)
    assert r.status_code == 409 and r.json()["error"]["code"] == "DOCUMENT_LOCKED"  # linked to a step
    r = await client.post(f"{API}/documents/templates/{fai['id']}/preview", headers=owner.headers, json={"context": {}})
    assert "No value for {{run.title}} in this context" in r.json()["warnings"]


async def test_templates_system_immutable_and_clone(client, owner):
    tpl = (await client.get(f"{API}/documents/templates", headers=owner.headers)).json()[0]
    assert tpl["is_system_default"]
    r = await client.patch(f"{API}/documents/templates/{tpl['id']}", headers=owner.headers, json={"name": "x"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "SYSTEM_RECORD"
    assert (await client.delete(f"{API}/documents/templates/{tpl['id']}", headers=owner.headers)).status_code == 409
    clone = (await client.post(f"{API}/documents/templates/{tpl['id']}/clone", headers=owner.headers)).json()
    assert clone["is_system_default"] is False and clone["name"].startswith("Copy of")
    bad = {"content_schema": {"blocks": [{"id": "a", "type": "paragraph"}, {"id": "a", "type": "paragraph"}]}}
    assert (
        await client.patch(f"{API}/documents/templates/{clone['id']}", headers=owner.headers, json=bad)
    ).status_code == 400
    r = await client.patch(f"{API}/documents/templates/{clone['id']}", headers=owner.headers, json={"name": "Mine"})
    assert r.json()["name"] == "Mine"
    assert (await client.delete(f"{API}/documents/templates/{clone['id']}", headers=owner.headers)).status_code == 204


async def test_iso_approval_chain_sod_and_obsoleting(client, owner):
    qa = await add_member(owner.org_id, "QA_LEAD")
    qa2 = await add_member(owner.org_id, "QA_LEAD")
    sop = next(f for f in await _folders(client, owner) if f["system_kind"] == "MASTER_LIBRARY")
    r = await client.post(f"{API}/documents", headers=owner.headers,
                          json={"folder_id": sop["id"], "title": "Cutting SOP", "source_type": "BLANK_ADHOC",
                                "iso_doc_number": "SOP-007",
                                "rich_content": {"blocks": [{"id": "p", "type": "paragraph", "data": {"text": "v1"}}]}})  # fmt: skip
    assert r.status_code == 201, r.text
    d1 = r.json()
    tr = f"{API}/documents/{d1['id']}/transition"
    assert (await client.post(tr, headers=owner.headers, json={"to": "APPROVED"})).status_code == 409
    assert (await client.post(tr, headers=owner.headers, json={"to": "UNDER_REVIEW"})).json()[
        "approval_status"
    ] == "UNDER_REVIEW"
    r = await client.patch(f"{API}/documents/{d1['id']}", headers=owner.headers, json={"rich_content": {"blocks": []}})
    assert r.status_code == 409 and r.json()["error"]["code"] == "DOCUMENT_LOCKED"
    r = await client.post(f"{API}/documents/{d1['id']}/review", headers=owner.headers, json={"comment": "self"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "SEGREGATION_OF_DUTIES"
    r = await client.post(tr, headers=qa.headers, json={"to": "APPROVED"})
    assert r.status_code == 409  # not reviewed yet
    r = await client.post(f"{API}/documents/{d1['id']}/review", headers=qa.headers, json={"comment": "Looks good"})
    assert r.status_code == 200 and r.json()["reviewed_by_name"]
    r = await client.post(tr, headers=qa.headers, json={"to": "APPROVED"})
    assert r.status_code == 200 and r.json()["approval_status"] == "APPROVED" and r.json()["approved_by_name"]
    assert (await client.delete(f"{API}/documents/{d1['id']}", headers=owner.headers)).json()["error"][
        "code"
    ] == "DOCUMENT_LOCKED"

    r = await client.post(f"{API}/documents/{d1['id']}/revise", headers=qa.headers, json={})
    assert r.status_code == 201, r.text
    d2 = r.json()["document"]
    assert d2["revision_no"] == 2 and d2["approval_status"] == "DRAFT" and d2["previous_revision_id"] == d1["id"]
    assert (await client.post(f"{API}/documents/{d1['id']}/revise", headers=qa.headers, json={})).status_code == 409
    r = await client.patch(f"{API}/documents/{d2['id']}", headers=qa.headers,
                           json={"rich_content": {"blocks": [{"id": "p", "type": "paragraph", "data": {"text": "v2"}}]}})  # fmt: skip
    assert r.status_code == 200
    tr2 = f"{API}/documents/{d2['id']}/transition"
    await client.post(tr2, headers=qa.headers, json={"to": "UNDER_REVIEW"})
    r = await client.post(tr2, headers=qa2.headers, json={"to": "DRAFT"})
    assert r.status_code == 400  # rejection needs a comment
    r = await client.post(tr2, headers=qa2.headers, json={"to": "DRAFT", "comment": "Fix step 3"})
    assert r.json()["approval_status"] == "DRAFT" and r.json()["review_comment"] == "Fix step 3"
    await client.post(tr2, headers=qa.headers, json={"to": "UNDER_REVIEW"})
    await client.post(f"{API}/documents/{d2['id']}/review", headers=qa2.headers, json={})
    r = await client.post(tr2, headers=qa.headers, json={"to": "APPROVED"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "SEGREGATION_OF_DUTIES"  # qa prepared rev 2
    r = await client.post(tr2, headers=owner.headers, json={"to": "APPROVED"})
    assert r.status_code == 200, r.text
    old = (await client.get(f"{API}/documents/{d1['id']}", headers=owner.headers)).json()
    assert old["approval_status"] == "OBSOLETE"
    versions = (await client.get(f"{API}/documents/{d2['id']}/versions", headers=owner.headers)).json()
    assert [(v["revision_no"], v["approval_status"]) for v in versions] == [(2, "APPROVED"), (1, "OBSOLETE")]
    audit = (await client.get(f"{API}/documents/{d1['id']}/audit", headers=owner.headers)).json()
    assert {"TRANSITION", "CREATE"} <= {a["action"] for a in audit}
    assert any(a["after_diff"] == {"approval_status": "OBSOLETE", "revision_no": 1} for a in audit)
    obsolete_pdf = await client.get(f"{API}/documents/{d1['id']}/export?format=docx", headers=owner.headers)
    assert obsolete_pdf.status_code == 200 and obsolete_pdf.content[:2] == b"PK"


async def test_folder_acl_override_hides_folder(client, owner):
    accountant = await add_member(owner.org_id, "ACCOUNTANT")
    tree = await _month(client, owner)
    month, payroll = tree[0], next(f for f in tree if f["system_kind"] == "PAYROLL")
    await _upload(client, owner, payroll["id"], title="Salary register")
    role = (await sql("SELECT id FROM org_roles WHERE org_id = :o AND role_code = 'ACCOUNTANT'", o=owner.org_id))[0][0]
    await sql("INSERT INTO resource_acl (org_id, subject_type, subject_id, resource_type, resource_id, access_level) "
              "VALUES (:o, 'ROLE', :r, 'DOC_FOLDER', :f, 'NONE')", o=owner.org_id, r=role, f=payroll["id"])  # fmt: skip
    names = [f["name"] for f in await _folders(client, accountant, month["id"])]
    assert "Payroll & Statutory Challans" not in names and "Bills & Vouchers" in names
    assert (await client.get(f"{API}/documents/folders/{payroll['id']}", headers=accountant.headers)).status_code == 404
    hits = (await client.get(f"{API}/documents/search?q=salary", headers=accountant.headers)).json()
    assert hits == []
    assert len((await client.get(f"{API}/documents/search?q=salary", headers=owner.headers)).json()) == 1


async def test_cross_tenant_document_404(client, owner):
    from tests.factories import org_with_owner

    other = await org_with_owner(client)
    bills = (await _month(client, owner))[1]
    doc = await _upload(client, owner, bills["id"])
    assert (await client.get(f"{API}/documents/{doc['id']}", headers=other.headers)).status_code == 404
    assert (await client.get(f"{API}/documents/folders/{bills['id']}", headers=other.headers)).status_code == 404


async def test_platform_push_helpers(client, owner):
    from app.core.context import TenantContext
    from app.core.db import get_sessionmaker, set_tenant_scope
    from app.modules.documents import interface as documents
    from app.modules.operations import interface as operations
    from app.seeds.doc_templates import BATCH_SUMMARY
    from app.seeds.iso_workflows import ASSEMBLY_AND_TEST

    await client.post(f"{API}/documents/templates", headers=owner.headers,
                      json={"template_type": "MONTHLY_FOLDER_RULE", "name": "x", "content_schema": {"custom": ["POs"]}})  # fmt: skip
    ctx = TenantContext.system(owner.org_id)
    async with get_sessionmaker()() as s, s.begin():
        await set_tenant_scope(s, owner.org_id, None)
        assert await operations.install_platform_workflow_template(s, ctx, ASSEMBLY_AND_TEST["key"], ASSEMBLY_AND_TEST)
        assert await documents.upsert_platform_doc_template(
            s, ctx, BATCH_SUMMARY["key"], {**BATCH_SUMMARY, "name": "Batch v2"}
        )
        assert await documents.apply_monthly_folder_rule(
            s, ctx, {"subfolders": [{"name": "Bills", "system_kind": "BILLS"}]}
        )
    wfs = (await client.get(f"{API}/operations/workflows", headers=owner.headers)).json()
    assert any(w["name"] == ASSEMBLY_AND_TEST["name"] and w["status"] == "DRAFT" for w in wfs)
    tpls = (await client.get(f"{API}/documents/templates", headers=owner.headers)).json()
    assert [t["name"] for t in tpls if t["name"].startswith("Batch")] == ["Batch v2"]
    rule = next(t for t in tpls if t["template_type"] == "MONTHLY_FOLDER_RULE" and t["is_system_default"])
    assert rule["content_schema"]["subfolders"][0]["name"] == "Bills"
