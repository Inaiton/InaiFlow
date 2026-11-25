import { describe, expect, it } from "vitest";
import { defaultPeriod, fyQuarters, monthPeriod, periodFromParams, periodLabel } from "./period";

const fy = { start: "2026-04-01", end: "2027-03-31" };
const params = (o: Record<string, string>) => ({ get: (k: string) => o[k] ?? null });

describe("period", () => {
  it("defaults to FY start → today", () => {
    expect(defaultPeriod(fy, "2026-11-24")).toEqual({ from: "2026-04-01", to: "2026-11-24" });
    expect(defaultPeriod(fy, "2027-06-01")).toEqual({ from: "2026-04-01", to: "2027-03-31" });
  });
  it("reads valid params only", () => {
    const fb = defaultPeriod(fy, "2026-11-24");
    expect(periodFromParams(params({ from: "2026-05-01", to: "2026-05-31" }), fb)).toEqual({ from: "2026-05-01", to: "2026-05-31" });
    expect(periodFromParams(params({ from: "2026-06-01", to: "2026-05-31" }), fb)).toBe(fb);
    expect(periodFromParams(params({ from: "x", to: "2026-05-31" }), fb)).toBe(fb);
  });
  it("labels and months", () => {
    expect(periodLabel({ from: "2026-04-01", to: "2027-03-31" })).toBe("1-Apr-26 to 31-Mar-27");
    expect(monthPeriod("2026-02")).toEqual({ from: "2026-02-01", to: "2026-02-28" });
    expect(monthPeriod("2026-12")).toEqual({ from: "2026-12-01", to: "2026-12-31" });
    expect(fyQuarters("2026-04-01")[3]?.label).toBe("Q4 · Jan–Mar 2027");
  });
});
