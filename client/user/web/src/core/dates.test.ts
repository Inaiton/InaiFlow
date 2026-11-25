import { describe, expect, it } from "vitest";
import { fyForDate, fyProgress, monthKey, monthLabel, monthsOfFy } from "./dates";

describe("dates", () => {
  it("computes Indian FY", () => {
    expect(fyForDate("2026-09-15")).toEqual({ label: "FY 2026-27", start: "2026-04-01", end: "2027-03-31" });
    expect(fyForDate("2027-02-01").label).toBe("FY 2026-27");
    expect(fyForDate("2026-04-01").start).toBe("2026-04-01");
    expect(fyForDate("2026-06-01", 1)).toEqual({ label: "FY 2026", start: "2026-01-01", end: "2026-12-31" });
  });
  it("lists months", () => {
    const m = monthsOfFy({ start: "2026-04-01" });
    expect(m).toHaveLength(12);
    expect(m[0]).toBe("2026-04");
    expect(m[11]).toBe("2027-03");
    expect(monthKey("2026-09-30")).toBe("2026-09");
    expect(monthLabel("2026-09")).toBe("Sept 2026");
  });
  it("progress is clamped", () => {
    const fy = { start: "2026-04-01", end: "2027-03-31" };
    expect(fyProgress(fy, new Date(2025, 0, 1))).toBe(0);
    expect(fyProgress(fy, new Date(2028, 0, 1))).toBe(100);
  });
});
