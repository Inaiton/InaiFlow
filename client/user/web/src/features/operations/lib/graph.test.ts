import { describe, expect, it } from "vitest";
import { issuesByNode, reachable, takenEdges, topoOrder, validateGraph, type StepOut, type WorkflowGraph, type WorkflowNode } from "./graph";

const node = (id: string, shape: WorkflowNode["shape"], config: WorkflowNode["config"] = {}): WorkflowNode => ({ id, shape, label: id, position: { x: "0", y: "0" }, config });
const g: WorkflowGraph = {
  nodes: [node("end", "TERMINATOR"), node("gate", "DIAMOND", { qc_fields: [{ key: "b", label: "Bore", type: "NUMBER", nominal: "40" }], reject_action: "SCRAP_NCR" }), node("start", "OVAL"), node("cnc", "RECTANGLE")],
  edges: [
    { id: "e1", source: "start", target: "cnc", branch: "PASS" },
    { id: "e2", source: "cnc", target: "gate", branch: "PASS" },
    { id: "e3", source: "gate", target: "end", branch: "PASS" },
    { id: "e4", source: "gate", target: "cnc", branch: "REWORK" },
  ],
};

describe("graph helpers", () => {
  it("orders topologically ignoring rework loops", () => {
    expect(topoOrder(g)).toEqual(["start", "cnc", "gate", "end"]);
  });
  it("finds reachable nodes", () => {
    const g2 = { ...g, nodes: [...g.nodes, node("orphan", "RECTANGLE")] };
    expect(reachable(g2).has("orphan")).toBe(false);
    expect(reachable(g2).has("end")).toBe(true);
  });
  it("a valid graph has no errors", () => {
    expect(validateGraph(g).errors).toEqual([]);
  });
  it("flags missing start/end, dead ends and orphans", () => {
    const bad: WorkflowGraph = { nodes: [node("a", "RECTANGLE"), node("b", "DIAMOND")], edges: [] };
    const { errors, warnings } = validateGraph(bad);
    const msgs = errors.map((e) => e.message).join("|");
    expect(msgs).toMatch(/Start/);
    expect(msgs).toMatch(/End step/);
    expect(issuesByNode(errors).get("a")?.length).toBeGreaterThan(0);
    expect(warnings.some((w) => w.node_id === "b")).toBe(true);
  });
  it("flags outgoing edges from an end step and duplicate QC keys", () => {
    const dup: WorkflowGraph = {
      nodes: [node("s", "OVAL"), node("x", "RECTANGLE", { qc_fields: [{ key: "k", label: "A", type: "TEXT" }, { key: "k", label: "B", type: "TEXT" }] }), node("e", "TERMINATOR")],
      edges: [{ id: "1", source: "s", target: "x", branch: "PASS" }, { id: "2", source: "x", target: "e", branch: "PASS" }, { id: "3", source: "e", target: "x", branch: "DEFAULT" }],
    };
    const msgs = validateGraph(dup).errors.map((e) => e.message);
    expect(msgs.some((m) => /End steps/.test(m))).toBe(true);
    expect(msgs.some((m) => /same key/.test(m))).toBe(true);
  });
  it("computes taken edges from executed steps", () => {
    const step = (node_id: string, p: Partial<StepOut>): StepOut => ({
      id: node_id, node_id, step_name: node_id, node_shape: "RECTANGLE", sequence: 0, status: "PASSED", input_qty: "0", accepted_qty: "0", rejected_qty: "0", rework_qty: "0",
      qc_measurements: {}, branch_taken: null, quick_qc: false, is_locked: false, executed_by_name: null, executed_at: "2026-11-01T00:00:00Z", signed_off_by_name: null, signed_off_at: null,
      override_reason: null, skip_reason: null, notes: null, instrument_id: null, ncr_id: null, attachment_count: 0, ...p,
    });
    const steps = [step("start", { input_qty: "500", accepted_qty: "500" }), step("cnc", { input_qty: "500", accepted_qty: "500" }), step("gate", { input_qty: "500", accepted_qty: "485", rework_qty: "15" }), step("end", { status: "ACTIVE", executed_at: null })];
    const t = takenEdges(g, steps);
    expect(t.get("e3")).toBe("485");
    expect(t.get("e4")).toBe("15");
    expect(t.has("e1")).toBe(true);
  });
});
