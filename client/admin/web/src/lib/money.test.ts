import { describe, expect, it } from "vitest";
import { formatINR, formatINRCompact, formatRate, groupIndian, isDecimalString, normalizeDecimalInput, parseDecimal, sumDecimals, toDecimalString } from "./money";

describe("money", () => {
  it("validates decimal strings", () => {
    expect(isDecimalString("12.3456")).toBe(true);
    expect(isDecimalString("12.34567")).toBe(false);
    expect(isDecimalString("1e3")).toBe(false);
    expect(isDecimalString(12)).toBe(false);
  });
  it("round-trips through bigint", () => {
    expect(parseDecimal("1234.5")).toBe(12345000n);
    expect(parseDecimal("-0.0001")).toBe(-1n);
    expect(toDecimalString(12345000n)).toBe("1234.5000");
    expect(toDecimalString(12345n, 2)).toBe("1.23");
    expect(toDecimalString(12355n, 2)).toBe("1.24");
  });
  it("groups digits the Indian way", () => {
    expect(groupIndian("123")).toBe("123");
    expect(groupIndian("1234")).toBe("1,234");
    expect(groupIndian("12345678")).toBe("1,23,45,678");
  });
  it("formats INR", () => {
    expect(formatINR("250000.5")).toBe("₹ 2,50,000.50");
    expect(formatINR("-1500")).toBe("-₹ 1,500.00".replace("-₹ ", "-₹ "));
    expect(formatINR(null)).toBe("—");
    expect(formatINR("100", { symbol: false, dp: 0 })).toBe("100");
  });
  it("formats compact INR", () => {
    expect(formatINRCompact("18600000")).toBe("₹ 1.86 Cr");
    expect(formatINRCompact("450000")).toBe("₹ 4.50 L");
    expect(formatINRCompact("9999")).toBe("₹ 9,999");
  });
  it("sums without floats", () => {
    expect(sumDecimals(["0.1", "0.2"])).toBe("0.3000");
  });
  it("normalizes input", () => {
    expect(normalizeDecimalInput("1,20,000.50")).toBe("120000.5");
    expect(normalizeDecimalInput("abc")).toBeNull();
    expect(normalizeDecimalInput("0")).toBe("0");
  });
  it("formats rates", () => {
    expect(formatRate("18.0000")).toBe("18%");
    expect(formatRate("0.25")).toBe("0.25%");
  });
});
