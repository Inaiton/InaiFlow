import { describe, expect, it } from "vitest";
import { acceptRemainder, checkCounts } from "./quantities";

describe("checkCounts", () => {
  it("accepts a balanced entry", () => {
    const r = checkCounts({ input: "500", accepted: "485", rejected: "15", rework: "" });
    expect(r.ok).toBe(true);
    expect(r.remaining).toBe("0");
    expect(r.needsDefect).toBe(true);
  });
  it("reports units not yet counted", () => {
    const r = checkCounts({ input: "500", accepted: "400", rejected: "0", rework: "0" });
    expect(r.ok).toBe(false);
    expect(r.remaining).toBe("100");
    expect(r.errors.sum).toMatch(/100 units/);
  });
  it("reports over-counting", () => {
    const r = checkCounts({ input: "10", accepted: "8", rejected: "2", rework: "1" });
    expect(r.ok).toBe(false);
    expect(r.errors.sum).toMatch(/1 more/);
  });
  it("handles decimals exactly", () => {
    expect(checkCounts({ input: "0.3", accepted: "0.1", rejected: "0.2", rework: "" }).ok).toBe(true);
  });
  it("rejects negatives, junk and zero input", () => {
    expect(checkCounts({ input: "10", accepted: "-1", rejected: "11", rework: "" }).errors.accepted).toBeDefined();
    expect(checkCounts({ input: "abc", accepted: "0", rejected: "0", rework: "" }).errors.input).toBeDefined();
    expect(checkCounts({ input: "0", accepted: "0", rejected: "0", rework: "" }).errors.input).toBeDefined();
  });
  it("acceptRemainder fills accepted", () => {
    expect(acceptRemainder({ input: "500", accepted: "", rejected: "15", rework: "5" }).accepted).toBe("480");
    expect(acceptRemainder({ input: "5", accepted: "", rejected: "15", rework: "" }).accepted).toBe("0");
  });
});
