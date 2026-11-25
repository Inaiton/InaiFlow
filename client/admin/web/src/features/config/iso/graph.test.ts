import { describe, expect, it } from "vitest";
import { extractGraph, newNodeId, validateGraph, type Graph } from "./graph";

const pos = { x: "0", y: "0" };
const good: Graph = {
  nodes: [
    { id: "s", shape: "OVAL", label: "Start", position: pos, config: {} },
    { id: "q", shape: "DIAMOND", label: "QC", position: pos, config: {} },
    { id: "e", shape: "TERMINATOR", label: "End", position: pos, config: {} },
    { id: "x", shape: "TERMINATOR", label: "Scrap", position: pos, config: {} },
  ],
  edges: [
    { id: "1", source: "s", target: "q", branch: "DEFAULT" },
    { id: "2", source: "q", target: "e", branch: "PASS" },
    { id: "3", source: "q", target: "x", branch: "REJECT" },
  ],
};

describe("workflow graph", () => {
  it("extracts bare and wrapped graphs", () => {
    expect(extractGraph(good)?.meta).toBeNull();
    const w = extractGraph({ name: "T", graph_definition: good });
    expect(w?.graph.nodes).toHaveLength(4);
    expect(w?.wrap({ nodes: [], edges: [] })).toEqual({ name: "T", graph_definition: { nodes: [], edges: [] } });
    expect(extractGraph({ foo: 1 })).toBeNull();
  });
  it("validates", () => {
    expect(validateGraph(good)).toEqual([]);
    const bad = { ...good, edges: good.edges.filter((e) => e.branch !== "PASS") };
    expect(validateGraph(bad).map((i) => i.message)).toContain('QC gate "QC" needs a PASS branch.');
    expect(validateGraph({ nodes: [], edges: [] })).toHaveLength(2);
  });
  it("generates unique ids", () => {
    expect(newNodeId(good.nodes, "RECTANGLE")).toBe("rectangle_5");
  });
});
