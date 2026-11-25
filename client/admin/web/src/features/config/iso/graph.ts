import type { components } from "@/lib/api/schema";

export type Graph = components["schemas"]["WorkflowGraph"];
export type WNode = components["schemas"]["WorkflowNode"];
export type WEdge = components["schemas"]["WorkflowEdge"];
export type Shape = components["schemas"]["NodeShape"];
export type BranchT = components["schemas"]["Branch"];
export type QcField = components["schemas"]["QcField"];

export const SHAPES: { shape: Shape; label: string; hint: string }[] = [
  { shape: "OVAL", label: "Start / trigger", hint: "Manual, scheduled or on GRN" },
  { shape: "RECTANGLE", label: "Process step", hint: "Shop-floor operation" },
  { shape: "DIAMOND", label: "QC gate", hint: "Pass / reject / rework decision" },
  { shape: "PARALLEL", label: "Parallel sub-process", hint: "Runs simultaneous checks" },
  { shape: "TERMINATOR", label: "End / commit", hint: "Commits finished units" },
];
export const BRANCHES: BranchT[] = ["PASS", "REJECT", "REWORK", "DEFAULT"];
export const BRANCH_COLOR: Record<BranchT, string> = { PASS: "#12B76A", REJECT: "#F04438", REWORK: "#F79009", DEFAULT: "#667085" };

const isObj = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);
const isGraph = (v: unknown): v is Graph => isObj(v) && Array.isArray(v.nodes) && Array.isArray(v.edges);

/** ISO template payload is either a bare WorkflowGraph or `{ name, description, iso_clause_ref, graph_definition }`. */
export function extractGraph(payload: unknown): { graph: Graph; wrap: (g: Graph) => unknown; meta: Record<string, unknown> | null } | null {
  if (isGraph(payload)) return { graph: payload, wrap: (g) => ({ ...payload, ...g }), meta: null };
  if (isObj(payload) && isGraph(payload.graph_definition)) return { graph: payload.graph_definition, wrap: (g) => ({ ...payload, graph_definition: g }), meta: payload };
  return null;
}

export function newNodeId(nodes: WNode[], shape: Shape): string {
  const base = shape.toLowerCase();
  let i = nodes.length + 1;
  while (nodes.some((n) => n.id === `${base}_${i}`)) i++;
  return `${base}_${i}`;
}

export function defaultConfig(shape: Shape): WNode["config"] {
  switch (shape) {
    case "OVAL":
      return { trigger: "MANUAL" };
    case "DIAMOND":
      return { qc_fields: [], pass_criteria: { mode: "ALL_IN_TOLERANCE" }, reject_action: "NCR" };
    case "TERMINATOR":
      return {};
    default:
      return { assigned_role_code: "OPERATOR", qc_fields: [], skippable: false, instrument_required: false };
  }
}

export interface Issue {
  node_id: string | null;
  edge_id: string | null;
  message: string;
}

/** Client-side structural checks (the tenant server re-validates on publish). */
export function validateGraph(g: Graph): Issue[] {
  const issues: Issue[] = [];
  const ids = new Set(g.nodes.map((n) => n.id));
  if (!g.nodes.some((n) => n.shape === "OVAL")) issues.push({ node_id: null, edge_id: null, message: "Add a Start (oval) node." });
  if (!g.nodes.some((n) => n.shape === "TERMINATOR")) issues.push({ node_id: null, edge_id: null, message: "Add an End (terminator) node." });
  if (ids.size !== g.nodes.length) issues.push({ node_id: null, edge_id: null, message: "Node ids must be unique." });
  for (const e of g.edges) {
    if (!ids.has(e.source) || !ids.has(e.target)) issues.push({ node_id: null, edge_id: e.id, message: `Edge ${e.id} points to a missing node.` });
  }
  for (const n of g.nodes) {
    if (!n.label.trim()) issues.push({ node_id: n.id, edge_id: null, message: `Node ${n.id} needs a label.` });
    const out = g.edges.filter((e) => e.source === n.id);
    if (n.shape !== "TERMINATOR" && out.length === 0) issues.push({ node_id: n.id, edge_id: null, message: `"${n.label}" has no outgoing edge.` });
    // Rejected units go to scrap/NCR per reject_action, so only a PASS branch is mandatory on a QC gate.
    if (n.shape === "DIAMOND" && !out.some((e) => e.branch === "PASS")) issues.push({ node_id: n.id, edge_id: null, message: `QC gate "${n.label}" needs a PASS branch.` });
    const keys = (n.config.qc_fields ?? []).map((f) => f.key);
    if (new Set(keys).size !== keys.length) issues.push({ node_id: n.id, edge_id: null, message: `"${n.label}" has duplicate QC field keys.` });
  }
  return issues;
}
