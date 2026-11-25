import { describe, expect, it } from "vitest";
import { diffJson } from "./json-diff";

describe("diffJson", () => {
  it("finds nested changes", () => {
    const rows = diffJson({ a: 1, b: { c: "x", d: [1, 2] } }, { a: 1, b: { c: "y", d: [1] }, e: true });
    expect(rows).toEqual([
      { path: "b.c", kind: "changed", before: "x", after: "y" },
      { path: "b.d[1]", kind: "removed", before: 2 },
      { path: "e", kind: "added", after: true },
    ]);
  });
  it("handles null sides", () => {
    expect(diffJson(undefined, { a: 1 })).toEqual([{ path: "(root)", kind: "added", after: { a: 1 } }]);
    expect(diffJson({ a: 1 }, { a: 1 })).toEqual([]);
  });
});
