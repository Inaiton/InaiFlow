"""Operations test helpers: graphs, stock items, published workflows, runs and step execution."""

from __future__ import annotations

import uuid
from typing import Any

from tests.factories import API, sql, unique

OD = {"key": "od", "label": "Outer diameter", "type": "NUMBER", "unit": "mm", "nominal": "25.00",
      "tol_minus": "0.02", "tol_plus": "0.02", "required": True}  # fmt: skip


def node(nid: str, shape: str, label: str, **config: Any) -> dict[str, Any]:
    return {"id": nid, "shape": shape, "label": label, "position": {"x": "0", "y": "0"}, "config": config}


def edge(s: str, t: str, branch: str = "PASS") -> dict[str, Any]:
    return {"id": f"{s}-{t}-{branch}", "source": s, "target": t, "branch": branch, "label": None}


def simple_graph() -> dict[str, Any]:
    return {
        "nodes": [node("start", "OVAL", "Start"), node("cut", "RECTANGLE", "CNC Cut"),
                  node("qc", "DIAMOND", "QC Gate", qc_fields=[OD], pass_criteria={"mode": "ALL_FIELDS_IN_TOLERANCE"},
                       reject_action="SCRAP_NCR", instrument_required=True),
                  node("end", "TERMINATOR", "Commit FG")],
        "edges": [edge("start", "cut"), edge("cut", "qc"), edge("qc", "end"), edge("qc", "cut", "REWORK")],
    }  # fmt: skip


# ---------------------------------------------------------------- API helpers
async def stock_item(org_id: uuid.UUID, name: str | None = None, rate: str = "10", bom: Any = None) -> uuid.UUID:
    import json

    rows = await sql("INSERT INTO stock_items (org_id, name, sku_code, opening_rate, bom_components, custom_fields) "
                     "VALUES (:o, :n, :s, CAST(:r AS numeric), CAST(:b AS jsonb), CAST(:c AS jsonb)) RETURNING id",
                     o=org_id, n=name or unique("Item "), s=unique("SKU-"), r=rate, b=json.dumps(bom or []),
                     c=json.dumps({"drawing_rev": "C"}))  # fmt: skip
    return rows[0][0]


async def published_workflow(client, actor, graph: dict | None = None, **extra: Any) -> dict:  # noqa: ANN001
    r = await client.post(f"{API}/operations/workflows", headers=actor.headers,
                          json={"name": unique("WF "), "graph_definition": graph or simple_graph(), **extra})  # fmt: skip
    assert r.status_code == 201, r.text
    r = await client.post(f"{API}/operations/workflows/{r.json()['id']}/publish", headers=actor.headers)
    assert r.status_code == 200, r.text
    return r.json()


async def new_run(client, actor, wf: dict, qty: str = "100", **extra: Any) -> dict:  # noqa: ANN001
    body = {"workflow_id": wf["id"], "period_month": "2026-09-01", "planned_qty": qty, "run_title": unique("Run "),
            **extra}  # fmt: skip
    r = await client.post(f"{API}/operations/runs", headers=actor.headers, json=body)
    assert r.status_code == 201, r.text
    return r.json()


def step(run: dict, node_id: str) -> dict:
    return next(s for s in run["steps"] if s["node_id"] == node_id)


async def execute(client, actor, run: dict, node_id: str, **body: Any):  # noqa: ANN001,ANN201
    r = await client.get(f"{API}/operations/runs/{run['id']}", headers=actor.headers)
    sid = step(r.json(), node_id)["id"]
    return await client.post(f"{API}/operations/runs/{run['id']}/steps/{sid}/execute", headers=actor.headers, json=body)


async def get_run(client, actor, run: dict) -> dict:  # noqa: ANN001
    r = await client.get(f"{API}/operations/runs/{run['id']}", headers=actor.headers)
    assert r.status_code == 200, r.text
    return r.json()
