import { describe, expect, it } from "vitest";
import { extractBlocks, newBlockId } from "./blocks";

describe("report blocks", () => {
  const blocks = [{ id: "b1", type: "heading", data: { text: "x" } }];
  it("extracts from both shapes", () => {
    expect(extractBlocks({ blocks })?.blocks).toHaveLength(1);
    const w = extractBlocks({ name: "T", content_schema: { blocks } });
    expect(w?.wrap([])).toEqual({ name: "T", content_schema: { blocks: [] } });
    expect(extractBlocks({ blocks: [{ nope: 1 }] })).toBeNull();
    expect(extractBlocks(null)).toBeNull();
  });
  it("creates unique ids", () => {
    expect(newBlockId(blocks)).toBe("b2");
  });
});
