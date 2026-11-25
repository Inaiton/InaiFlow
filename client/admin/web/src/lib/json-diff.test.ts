import { describe, expect, it } from "vitest";
import { diffJson } from "./json-diff";

describe("diffJson", () => {
  it("returns nothing for equal values", () => {
    expect(diffJson({ a: [1, { b: 2 }] }, { a: [1, { b: 2 }] })).toEqual([]);
  });
  it("detects changes, additions and removals", () => {
    const d = diffJson({ a: 1, b: { c: "x" }, l: [1, 2] }, { a: 2, b: { d: true }, l: [1] });
    expect(d).toEqual([
      { path: "a", kind: "changed", before: 1, after: 2 },
      { path: "b.c", kind: "removed", before: "x" },
      { path: "b.d", kind: "added", after: true },
      { path: "l[1]", kind: "removed", before: 2 },
    ]);
  });
  it("handles null to value", () => {
    expect(diffJson(null, { a: 1 })).toEqual([{ path: "(root)", kind: "changed", before: null, after: { a: 1 } }]);
  });
});
