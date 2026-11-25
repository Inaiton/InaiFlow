import { describe, expect, it } from "vitest";
import { allocationError } from "./alloc";

describe("allocationError", () => {
  it("requires 100% across distinct runs", () => {
    expect(allocationError([])).toBeNull();
    expect(allocationError([{ period_run_id: "a", share_pct: "60" }, { period_run_id: "b", share_pct: "40" }])).toBeNull();
    expect(allocationError([{ period_run_id: "a", share_pct: "60" }])).toBe("Shares must total 100%");
    expect(allocationError([{ period_run_id: "a", share_pct: "50" }, { period_run_id: "a", share_pct: "50" }])).toBe("Each run only once");
    expect(allocationError([{ period_run_id: "", share_pct: "100" }])).toBe("Pick a period run on every line");
  });
});
