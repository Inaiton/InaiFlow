import { describe, expect, it } from "vitest";
import { add, cmp, formatMoney, formatQty, fromScaled, isZero, mul, parseMoneyInput, round, sub, sum, toScaled } from "./money";

describe("money", () => {
  it("adds without float error", () => {
    expect(add("0.1", "0.2")).toBe("0.3");
    expect(add("100.0001", "-100")).toBe("0.0001");
    expect(sum(["1", "2.5", null, "3.25"])).toBe("6.75");
  });
  it("subtracts and compares", () => {
    expect(sub("10", "12.5")).toBe("-2.5");
    expect(cmp("1.10", "1.1")).toBe(0);
    expect(cmp("-1", "0")).toBe(-1);
    expect(isZero("0.0000")).toBe(true);
  });
  it("multiplies with 4dp half-up rounding", () => {
    expect(mul("2.5", "3")).toBe("7.5");
    expect(mul("1.0001", "1.0001")).toBe("1.0002");
    expect(mul("-0.00005", "1")).toBe("-0.0001");
    expect(mul("250000", "0.18")).toBe("45000");
  });
  it("round-trips scaled values", () => {
    expect(fromScaled(toScaled("-0.5"))).toBe("-0.5");
    expect(fromScaled(toScaled("12.34567"))).toBe("12.3457");
    expect(fromScaled(0n, 2)).toBe("0.00");
    expect(() => toScaled("1e5")).toThrow();
  });
  it("rounds to dp", () => {
    expect(round("2.345", 2)).toBe("2.35");
    expect(round("-2.345", 2)).toBe("-2.35");
    expect(round("7", 2)).toBe("7.00");
  });
  it("formats with Indian grouping", () => {
    expect(formatMoney("1234567")).toBe("₹12,34,567.00");
    expect(formatMoney("100")).toBe("₹100.00");
    expect(formatMoney("-250000.5")).toBe("-₹2,50,000.50");
    expect(formatMoney("-5", { parens: true, symbol: false })).toBe("(5.00)");
    expect(formatMoney("123456789.999")).toBe("₹12,34,56,790.00");
    expect(formatQty("1500.2500")).toBe("1,500.25");
  });
  it("parses user input", () => {
    expect(parseMoneyInput("₹ 12,34,567.5")).toBe("1234567.5");
    expect(parseMoneyInput("(25)")).toBe("-25");
    expect(parseMoneyInput("-0")).toBe("0");
    expect(parseMoneyInput(".5")).toBe("0.5");
    expect(parseMoneyInput("abc")).toBeNull();
    expect(parseMoneyInput("1.23456")).toBeNull();
    expect(parseMoneyInput("1.234", 2)).toBeNull();
    expect(parseMoneyInput("")).toBeNull();
  });
});
