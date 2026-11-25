import { describe, expect, it } from "vitest";
import { countNodes, moveAt, updateAt } from "./tree";

const tree = [{ name: "A", children: [{ name: "A1" }, { name: "A2" }] }, { name: "B" }];

describe("folder tree ops", () => {
  it("updates nested nodes", () => {
    const t = updateAt(tree, [0, 1], (n) => ({ ...n, name: "X" }));
    expect(t[0]!.children![1]!.name).toBe("X");
    expect(tree[0]!.children![1]!.name).toBe("A2");
  });
  it("removes nodes", () => {
    expect(updateAt(tree, [1], () => null)).toHaveLength(1);
  });
  it("moves nodes", () => {
    expect(moveAt(tree, [0, 0], 1)[0]!.children!.map((n) => n.name)).toEqual(["A2", "A1"]);
    expect(moveAt(tree, [0], -1)).toEqual(tree);
  });
  it("counts", () => {
    expect(countNodes(tree)).toBe(4);
  });
});
