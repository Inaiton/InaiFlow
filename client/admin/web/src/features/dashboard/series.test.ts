import { describe, expect, it } from "vitest";
import { sparkPath } from "./series";

describe("sparkPath", () => {
  it("builds a path", () => {
    const p = sparkPath([{ date: "2026-11-01", count: 0 }, { date: "2026-11-02", count: 10 }], 100, 50);
    expect(p.line).toBe("M4.0,46.0 L96.0,4.0");
    expect(p.area.endsWith("Z")).toBe(true);
    expect(sparkPath([], 10, 10).line).toBe("");
  });
});
