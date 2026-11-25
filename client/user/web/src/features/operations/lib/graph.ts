import type { Schemas } from "@/core/api/types";
import { cmp } from "@/core/money";

export type WorkflowGraph = Schemas["WorkflowGraph"];
export type WorkflowNode = Schemas["WorkflowNode"];
export type WorkflowEdge = Schemas["WorkflowEdge"];
export type NodeShape = Schemas["NodeShape"];
export type Branch = Schemas["Branch"];
export type ValidationIssue = Schemas["ValidationIssue"];
export type StepOut = Schemas["StepOut"];

const FORWARD: Branch[] = ["PASS", "DEFAULT"];

/** Topological order over forward edges (REWORK/REJECT loops ignored); cycles are appended in input order. */
export function topoOrder(g: WorkflowGraph): string[] {
  const ids = g.nodes.map((n) => n.id);
  const indeg = new Map(ids.map((id) => [id, 0]));
  const out = new Map<string, string[]>(ids.map((id) => [id, []]));
  for (const e of g.edges) {
    if (!FORWARD.includes(e.branch) || !indeg.has(e.source) || !indeg.has(e.target) || e.source === e.target) continue;
    out.get(e.source)!.push(e.target);
    indeg.set(e.target, (indeg.get(e.target) ?? 0) + 1);
  }
  const queue = ids.filter((id) => indeg.get(id) === 0);
  const order: string[] = [];
  while (queue.length) {
    const id = queue.shift()!;
    order.push(id);
    for (const t of out.get(id) ?? []) {
      indeg.set(t, (indeg.get(t) ?? 0) - 1);
      if (indeg.get(t) === 0) queue.push(t);
    }
  }
  for (const id of ids) if (!order.includes(id)) order.push(id);
  return order;
}

/** Node ids reachable from any OVAL start along any edge. */
export function reachable(g: WorkflowGraph): Set<string> {
  const seen = new Set<string>();
  const stack = g.nodes.filter((n) => n.shape === "OVAL").map((n) => n.id);
  while (stack.length) {
    const id = stack.pop()!;
    if (seen.has(id)) continue;
    seen.add(id);
    for (const e of g.edges) if (e.source === id) stack.push(e.target);
  }
  return seen;
}

/** Client-side hints shown on nodes while editing; the server's /validate is authoritative. */
export function validateGraph(g: WorkflowGraph): { errors: ValidationIssue[]; warnings: ValidationIssue[] } {
  const errors: ValidationIssue[] = [];
  const warnings: ValidationIssue[] = [];
  const err = (message: string, node_id: string | null = null, edge_id: string | null = null) => errors.push({ message, node_id, edge_id });
  const warn = (message: string, node_id: string | null = null) => warnings.push({ message, node_id, edge_id: null });
  const ids = new Set(g.nodes.map((n) => n.id));
  const starts = g.nodes.filter((n) => n.shape === "OVAL");
  if (g.nodes.length === 0) err("Add a Start step to begin");
  else if (starts.length === 0) err("Add a Start (oval) step");
  else if (starts.length > 1) warn("More than one Start step — runs will begin at each of them");
  if (g.nodes.length > 0 && !g.nodes.some((n) => n.shape === "TERMINATOR")) err("Add an End step so finished units are committed");
  for (const e of g.edges) {
    if (!ids.has(e.source) || !ids.has(e.target)) err("This connection points to a missing step", null, e.id);
  }
  const live = reachable(g);
  for (const n of g.nodes) {
    const outs = g.edges.filter((e) => e.source === n.id);
    const label = n.label.trim() || "Untitled step";
    if (!n.label.trim()) err("Give this step a name", n.id);
    if (n.shape !== "OVAL" && !live.has(n.id)) err(`“${label}” can’t be reached from Start`, n.id);
    if (n.shape === "TERMINATOR" && outs.length > 0) err("End steps can’t have outgoing connections", n.id);
    if (n.shape !== "TERMINATOR" && !outs.some((e) => FORWARD.includes(e.branch))) err(`“${label}” needs a PASS connection to the next step`, n.id);
    if (n.shape === "DIAMOND") {
      const fields = n.config.qc_fields ?? [];
      if (fields.length === 0) warn(`QC gate “${label}” has no QC fields — it will pass on counts only`, n.id);
      if (!outs.some((e) => e.branch === "REJECT") && !n.config.reject_action) warn(`Choose what happens to rejected units at “${label}”`, n.id);
    }
    const keys = (n.config.qc_fields ?? []).map((f) => f.key);
    if (new Set(keys).size !== keys.length) err("Two QC fields share the same key", n.id);
    for (const f of n.config.qc_fields ?? []) {
      if (!f.key.trim() || !f.label.trim()) err("Every QC field needs a key and a label", n.id);
      if ((f.type ?? "NUMBER") === "NUMBER" && !f.nominal) warn(`“${f.label || f.key}” has no nominal — Quick QC can’t fill it`, n.id);
    }
  }
  return { errors, warnings };
}

export function issuesByNode(issues: ValidationIssue[]): Map<string, string[]> {
  const m = new Map<string, string[]>();
  for (const i of issues) {
    if (!i.node_id) continue;
    m.set(i.node_id, [...(m.get(i.node_id) ?? []), i.message]);
  }
  return m;
}

/** Edges actually taken in a run, with the number of units that went along each. */
export function takenEdges(g: WorkflowGraph, steps: StepOut[]): Map<string, string> {
  const byNode = new Map(steps.map((s) => [s.node_id, s]));
  const taken = new Map<string, string>();
  for (const e of g.edges) {
    const s = byNode.get(e.source);
    if (!s || s.status === "PENDING" || (s.status === "ACTIVE" && !s.executed_at)) continue;
    const qty = s.status === "SKIPPED" ? s.input_qty
      : e.branch === "REJECT" ? s.rejected_qty
      : e.branch === "REWORK" ? s.rework_qty
      : s.accepted_qty;
    if (cmp(qty, "0") > 0) taken.set(e.id, qty);
  }
  return taken;
}

let counter = 0;
/** Unique, readable node id ("rect-3k2"). */
export function newNodeId(shape: NodeShape, existing: string[]): string {
  const base = shape.toLowerCase();
  let id = "";
  do id = `${base}-${(Date.now() + counter++).toString(36).slice(-4)}`;
  while (existing.includes(id));
  return id;
}

export const edgeId = (source: string, target: string, branch: Branch) => `e-${source}-${target}-${branch.toLowerCase()}`;

export const SHAPE_LABEL: Record<NodeShape, string> = {
  OVAL: "Start",
  RECTANGLE: "Process step",
  DIAMOND: "QC gate",
  PARALLEL: "Parallel checks",
  TERMINATOR: "End",
};

export const SHAPE_HINT: Record<NodeShape, string> = {
  OVAL: "Where a run begins — manual, monthly or on goods receipt",
  RECTANGLE: "Shop-floor work with an owner, machine and cycle time",
  DIAMOND: "Checks readings and routes pass / reject / rework",
  PARALLEL: "Checks that happen at the same time",
  TERMINATOR: "Commits finished units to stock and closes costing",
};
