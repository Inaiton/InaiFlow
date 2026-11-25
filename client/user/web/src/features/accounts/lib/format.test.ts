import { describe, expect, it } from "vitest";
import { accDate, amt, amtOrBlank, drcr, humanize, inr, shortDate, signedDrCr } from "./format";

describe("accounts formatting", () => {
  it("formats Indian amounts", () => {
    expect(amt("1234567")).toBe("12,34,567.00");
    expect(inr("1234567.5")).toBe("₹12,34,567.50");
    expect(amtOrBlank("0")).toBe("");
    expect(amtOrBlank("10")).toBe("10.00");
  });
  it("adds Dr/Cr suffixes", () => {
    expect(drcr("642800", "DR")).toBe("6,42,800.00 Dr");
    expect(drcr("10", "CR", { symbol: true })).toBe("₹10.00 Cr");
    expect(drcr("-10", "DR")).toBe("10.00 Cr");
    expect(drcr("0", "CR")).toBe("0.00");
    expect(signedDrCr("-25")).toBe("25.00 Cr");
    expect(signedDrCr("25")).toBe("25.00 Dr");
  });
  it("formats dates and labels", () => {
    expect(accDate("2026-11-23")).toBe("23-Nov-2026");
    expect(shortDate("2026-04-01")).toBe("1-Apr-26");
    expect(accDate(null)).toBe("—");
    expect(humanize("SALES_ORDER")).toBe("Sales order");
  });
});

import { percentOf } from "./format";
describe("percentOf", () => {
  it("computes integer percentages without floats", () => {
    expect(percentOf("250", "1000")).toBe(25);
    expect(percentOf("1", "0")).toBe(0);
    expect(percentOf("1500", "1000")).toBe(150);
  });
});
