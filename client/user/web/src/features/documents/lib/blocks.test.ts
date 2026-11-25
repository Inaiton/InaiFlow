import { describe, expect, it } from "vitest";
import { blocksReducer, emptyBlock, kvRows, normalizeBlocks, qcRows, tokensIn, type ReportBlock } from "./blocks";

const b = (id: string, type = "paragraph", data: unknown = { text: id }): ReportBlock => ({ id, type, data });

describe("blocksReducer", () => {
  const s = [b("a"), b("b"), b("c")];
  it("adds at the end or after a block", () => {
    expect(blocksReducer(s, { type: "add", block: b("x") }).map((x) => x.id)).toEqual(["a", "b", "c", "x"]);
    expect(blocksReducer(s, { type: "add", block: b("x"), afterId: "a" }).map((x) => x.id)).toEqual(["a", "x", "b", "c"]);
  });
  it("removes and moves within bounds", () => {
    expect(blocksReducer(s, { type: "remove", id: "b" }).map((x) => x.id)).toEqual(["a", "c"]);
    expect(blocksReducer(s, { type: "move", id: "c", dir: -1 }).map((x) => x.id)).toEqual(["a", "c", "b"]);
    expect(blocksReducer(s, { type: "move", id: "a", dir: -1 })).toBe(s);
    expect(blocksReducer(s, { type: "move", id: "c", dir: 1 })).toBe(s);
  });
  it("updates data immutably", () => {
    const next = blocksReducer(s, { type: "update", id: "b", data: { text: "new" } });
    expect(next[1]!.data).toEqual({ text: "new" });
    expect(s[1]!.data).toEqual({ text: "b" });
  });
  it("replaces the whole list", () => {
    expect(blocksReducer(s, { type: "replace", blocks: [] })).toEqual([]);
  });
});

describe("block parsing", () => {
  it("normalizes API JSON defensively and de-duplicates ids", () => {
    const out = normalizeBlocks({ blocks: [{ id: "1", type: "heading", data: { text: "T" } }, { id: "1", type: "paragraph" }, { foo: 1 }, "junk"] });
    expect(out).toHaveLength(2);
    expect(out[0]!.id).not.toBe(out[1]!.id);
    expect(normalizeBlocks(null)).toEqual([]);
  });
  it("reads kv and qc rows in both shapes", () => {
    expect(kvRows(b("k", "kv", { rows: [{ label: "Item", value: 5 }] }))).toEqual([{ label: "Item", value: "5" }]);
    expect(qcRows(b("q", "qc_table", { rows: [{ parameter: "Bore", spec: "40 ± 0.02", observed: "40", auto_filled: true, result: "Pass" }] }))[0]!.auto).toBe(true);
    expect(qcRows(b("q", "qc_table", { rows: [["Bore", "40", "40.01", "AUTO", "Pass"]] }))[0]!.observed).toBe("40.01");
  });
  it("creates empty blocks and finds tokens", () => {
    expect(emptyBlock("kv").data).toEqual({ rows: [{ label: "", value: "" }] });
    expect(tokensIn([b("a", "paragraph", { text: "{{item.name}} / {{ run.period }}" }), b("k", "kv", { rows: [{ value: "{{item.name}}" }] })])).toEqual(["item.name", "run.period"]);
  });
});
