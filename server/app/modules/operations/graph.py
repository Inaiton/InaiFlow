"""Pure workflow-graph logic: validation, topological order and routing lookups (no I/O).

Graph format = contract ``WorkflowGraph`` (``{"nodes": [...], "edges": [...]}``). Forward edges are
PASS / DEFAULT / REJECT; REWORK edges are loops back to an upstream node and are ignored for ordering.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

from app.modules.operations.qc import CRITERIA_MODES, ExpressionError, parse_expression

SHAPES = frozenset({"OVAL", "RECTANGLE", "DIAMOND", "PARALLEL", "TERMINATOR"})
BRANCHES = frozenset({"PASS", "REJECT", "REWORK", "DEFAULT"})
FORWARD = frozenset({"PASS", "DEFAULT", "REJECT"})
FIELD_TYPES = frozenset({"NUMBER", "TEXT", "BOOL", "SELECT"})


@dataclass(frozen=True, slots=True)
class Issue:
    message: str
    node_id: str | None = None
    edge_id: str | None = None


@dataclass
class ValidationResult:
    errors: list[Issue] = field(default_factory=list)
    warnings: list[Issue] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return not self.errors


def nodes_of(graph: dict[str, Any] | None) -> list[dict[str, Any]]:
    return list((graph or {}).get("nodes") or [])


def edges_of(graph: dict[str, Any] | None) -> list[dict[str, Any]]:
    return list((graph or {}).get("edges") or [])


def node_map(graph: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {n["id"]: n for n in nodes_of(graph) if isinstance(n, dict) and "id" in n}


def config_of(node: dict[str, Any]) -> dict[str, Any]:
    return node.get("config") or {}


def _branch(edge: dict[str, Any]) -> str:
    return str(edge.get("branch") or "PASS")


def out_edges(graph: dict[str, Any], node_id: str, branches: frozenset[str] | set[str]) -> list[dict[str, Any]]:
    return [e for e in edges_of(graph) if e.get("source") == node_id and _branch(e) in branches]


def pass_targets(graph: dict[str, Any], node_id: str) -> list[str]:
    return [e["target"] for e in out_edges(graph, node_id, {"PASS", "DEFAULT"})]


def rework_target(graph: dict[str, Any], node_id: str) -> str | None:
    edges = out_edges(graph, node_id, {"REWORK"})
    return edges[0]["target"] if edges else None


def reject_targets(graph: dict[str, Any], node_id: str) -> list[str]:
    return [e["target"] for e in out_edges(graph, node_id, {"REJECT"})]


def start_nodes(graph: dict[str, Any]) -> list[str]:
    return [n["id"] for n in nodes_of(graph) if n.get("shape") == "OVAL"]


def _forward_adjacency(graph: dict[str, Any], ids: set[str]) -> dict[str, list[str]]:
    adj: dict[str, list[str]] = {i: [] for i in ids}
    for e in edges_of(graph):
        s, t = e.get("source"), e.get("target")
        if s in ids and t in ids and _branch(e) in FORWARD:
            adj[s].append(t)
    return adj


def topological_order(graph: dict[str, Any]) -> list[str]:
    """Kahn's algorithm over forward edges; ties keep the original node order. Nodes on a forward cycle
    (invalid graphs) are appended in original order so callers always get every node exactly once."""
    order_ix = {n["id"]: i for i, n in enumerate(nodes_of(graph))}
    ids = set(order_ix)
    adj = _forward_adjacency(graph, ids)
    indeg = dict.fromkeys(ids, 0)
    for s in adj:
        for t in adj[s]:
            indeg[t] += 1
    ready = sorted((i for i in ids if indeg[i] == 0), key=order_ix.__getitem__)
    out: list[str] = []
    while ready:
        cur = ready.pop(0)
        out.append(cur)
        for t in adj[cur]:
            indeg[t] -= 1
            if indeg[t] == 0:
                ready.append(t)
                ready.sort(key=order_ix.__getitem__)
    seen = set(out)
    out += sorted((i for i in ids if i not in seen), key=order_ix.__getitem__)
    return out


def _reachable(adj: dict[str, list[str]], starts: list[str]) -> set[str]:
    seen: set[str] = set()
    queue = deque(starts)
    while queue:
        cur = queue.popleft()
        if cur in seen:
            continue
        seen.add(cur)
        queue.extend(adj.get(cur, []))
    return seen


def _has_forward_cycle(adj: dict[str, list[str]]) -> bool:
    state: dict[str, int] = {}

    def visit(n: str) -> bool:
        state[n] = 1
        for t in adj.get(n, []):
            if state.get(t) == 1 or (state.get(t) is None and visit(t)):
                return True
        state[n] = 2
        return False

    return any(state.get(n) is None and visit(n) for n in list(adj))


def _dec(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    if isinstance(value, float):
        raise InvalidOperation
    return Decimal(str(value))


def _validate_qc_fields(node: dict[str, Any], res: ValidationResult) -> list[str]:
    nid = node["id"]
    keys: list[str] = []
    for f in config_of(node).get("qc_fields") or []:
        key = (f or {}).get("key")
        if not key or not isinstance(key, str):
            res.errors.append(Issue("QC field needs a key", nid))
            continue
        if key in keys:
            res.errors.append(Issue(f"Duplicate QC field key '{key}'", nid))
        keys.append(key)
        ftype = str(f.get("type") or "NUMBER").upper()
        if ftype not in FIELD_TYPES:
            res.errors.append(Issue(f"QC field '{key}' has unknown type '{f.get('type')}'", nid))
        try:
            nominal, minus, plus = _dec(f.get("nominal")), _dec(f.get("tol_minus")), _dec(f.get("tol_plus"))
        except (InvalidOperation, ValueError, TypeError):
            res.errors.append(Issue(f"QC field '{key}' tolerances must be numeric", nid))
            continue
        if (minus is not None and minus < 0) or (plus is not None and plus < 0):
            res.errors.append(Issue(f"QC field '{key}' tolerances cannot be negative", nid))
        if (minus is not None or plus is not None) and nominal is None:
            res.errors.append(Issue(f"QC field '{key}' has tolerances but no nominal value", nid))
    return keys


def _validate_criteria(node: dict[str, Any], keys: list[str], res: ValidationResult) -> None:
    nid = node["id"]
    crit = config_of(node).get("pass_criteria") or {}
    mode = str(crit.get("mode") or "ALL_FIELDS_IN_TOLERANCE").upper()
    if mode not in CRITERIA_MODES:
        res.errors.append(Issue(f"Unknown pass criteria mode '{crit.get('mode')}'", nid))
        return
    if mode == "EXPRESSION":
        expr = crit.get("expression")
        if not expr:
            res.errors.append(Issue("EXPRESSION criteria need an expression", nid))
            return
        try:
            names = parse_expression(str(expr)).names()
        except ExpressionError as exc:
            res.errors.append(Issue(f"Invalid expression: {exc}", nid))
            return
        unknown = sorted(n for n in names if n not in keys and n not in {"accepted", "rejected", "rework", "input"})
        if unknown:
            res.errors.append(Issue(f"Expression uses unknown fields: {', '.join(unknown)}", nid))


def validate_graph(graph: dict[str, Any] | None) -> ValidationResult:
    res = ValidationResult()
    if not isinstance(graph, dict):
        res.errors.append(Issue("Graph must be an object with nodes and edges"))
        return res
    nodes, edges = nodes_of(graph), edges_of(graph)
    ids: list[str] = []
    for n in nodes:
        nid = n.get("id") if isinstance(n, dict) else None
        if not nid or not isinstance(nid, str):
            res.errors.append(Issue("Every node needs a string id"))
            continue
        if nid in ids:
            res.errors.append(Issue(f"Duplicate node id '{nid}'", nid))
        ids.append(nid)
        if n.get("shape") not in SHAPES:
            res.errors.append(Issue(f"Unknown shape '{n.get('shape')}'", nid))
    idset = set(ids)
    shapes = {n["id"]: n.get("shape") for n in nodes if isinstance(n, dict) and n.get("id")}
    starts = [i for i in ids if shapes.get(i) == "OVAL"]
    if not starts:
        res.errors.append(Issue("The workflow needs at least one Start (oval) node"))
    if not any(shapes.get(i) == "TERMINATOR" for i in ids):
        res.errors.append(Issue("The workflow needs at least one End (terminator) node"))

    edge_ids: set[str] = set()
    good_edges: list[dict[str, Any]] = []
    for e in edges:
        eid = e.get("id")
        if not eid:
            res.errors.append(Issue("Every edge needs an id"))
            continue
        if eid in edge_ids:
            res.errors.append(Issue(f"Duplicate edge id '{eid}'", edge_id=eid))
        edge_ids.add(eid)
        if _branch(e) not in BRANCHES:
            res.errors.append(Issue(f"Unknown branch '{e.get('branch')}'", edge_id=eid))
        if e.get("source") not in idset or e.get("target") not in idset:
            res.errors.append(Issue("Edge points to a node that does not exist", edge_id=eid))
            continue
        if e.get("source") == e.get("target"):
            res.errors.append(Issue("An edge cannot connect a node to itself", e.get("source"), eid))
            continue
        good_edges.append(e)

    clean = {"nodes": [n for n in nodes if isinstance(n, dict) and n.get("id") in idset], "edges": good_edges}
    adj = _forward_adjacency(clean, idset)
    if _has_forward_cycle(adj):
        res.errors.append(Issue("Forward edges form a loop; use a REWORK edge to go back upstream"))
    all_adj: dict[str, list[str]] = {i: [] for i in idset}
    for e in good_edges:
        all_adj[e["source"]].append(e["target"])
    reachable = _reachable(all_adj, starts)
    for i in ids:
        if starts and i not in reachable:
            res.errors.append(Issue("Node is not reachable from a Start node", i))

    for e in good_edges:
        if _branch(e) == "REWORK":
            if e["source"] not in _reachable(adj, [e["target"]]):
                res.errors.append(Issue("REWORK edges must point to an upstream step", e["source"], e["id"]))
        if _branch(e) == "REJECT" and shapes.get(e["source"]) != "DIAMOND":
            res.warnings.append(Issue("REJECT edges are only used by QC gates (diamonds)", e["source"], e["id"]))
    for e in good_edges:
        if shapes.get(e["target"]) == "OVAL":
            res.errors.append(Issue("Start nodes cannot have incoming edges", e["target"], e["id"]))

    for n in clean["nodes"]:
        nid, shape = n["id"], n.get("shape")
        keys = _validate_qc_fields(n, res)
        fwd_out = [e for e in good_edges if e["source"] == nid and _branch(e) in {"PASS", "DEFAULT"}]
        if shape == "DIAMOND":
            if not fwd_out:
                res.errors.append(Issue("QC gate needs a PASS edge", nid))
            _validate_criteria(n, keys, res)
            if not keys and str((config_of(n).get("pass_criteria") or {}).get("mode") or "").upper() in (
                "", "ALL_FIELDS_IN_TOLERANCE", "ALL_IN_TOLERANCE"
            ):  # fmt: skip
                res.warnings.append(Issue("QC gate has no QC fields; every reading check passes", nid))
        elif shape == "TERMINATOR":
            if any(e["source"] == nid for e in good_edges):
                res.warnings.append(Issue("End nodes should not have outgoing edges", nid))
        elif shape in SHAPES and not fwd_out:
            res.errors.append(Issue("Step has no outgoing PASS edge (dead end)", nid))
        if not str(n.get("label") or "").strip():
            res.warnings.append(Issue("Node has no label", nid))
    return res
