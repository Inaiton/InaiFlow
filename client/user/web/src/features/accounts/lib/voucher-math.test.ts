import { describe, expect, it } from "vitest";
import { applyTds, balancingLine, billAllocationsValid, billRemaining, invoiceSubtotal, lineAmount, voucherTotals } from "./voucher-math";

describe("voucherTotals", () => {
  it("balances Dr and Cr", () => {
    const t = voucherTotals([
      { side: "DR", amount: "72400" }, { side: "DR", amount: "14000" },
      { side: "CR", amount: "72400" }, { side: "CR", amount: "14000.00" },
    ]);
    expect(t).toEqual({ debit: "86400", credit: "86400", difference: "0", balanced: true });
  });
  it("flags imbalance and ignores blanks", () => {
    const t = voucherTotals([{ side: "DR", amount: "100.10" }, { side: "CR", amount: "" }, { side: "CR", amount: "40" }]);
    expect(t.balanced).toBe(false);
    expect(t.difference).toBe("60.1");
  });
  it("is not balanced when empty", () => {
    expect(voucherTotals([]).balanced).toBe(false);
  });
  it("suggests the balancing line", () => {
    expect(balancingLine([{ side: "DR", amount: "500" }, { side: "CR", amount: "200" }])).toEqual({ side: "CR", amount: "300" });
    expect(balancingLine([{ side: "CR", amount: "50" }])).toEqual({ side: "DR", amount: "50" });
    expect(balancingLine([{ side: "CR", amount: "50" }, { side: "DR", amount: "50" }])).toBeNull();
  });
});

describe("invoice lines", () => {
  it("computes qty × rate with discount", () => {
    expect(lineAmount("150", "1443")).toBe("216450.00");
    expect(lineAmount("20", "1425", "2")).toBe("27930.00");
    expect(lineAmount("3", "33.333")).toBe("100.00");
    expect(lineAmount("", "10")).toBe("0.00");
  });
  it("sums the taxable value", () => {
    expect(invoiceSubtotal([{ amount: "216450.00" }, { amount: "27930" }, { amount: "2500" }, { amount: null }])).toBe("246880.00");
  });
});

describe("bill allocations", () => {
  it("tracks remaining and validity", () => {
    expect(billRemaining("1000", [{ amount: "400" }, { amount: "100" }])).toBe("500");
    expect(billAllocationsValid("1000", [{ amount: "1000", ref_name: "SI/1" }])).toBe(true);
    expect(billAllocationsValid("1000", [{ amount: "1200", ref_name: "SI/1" }])).toBe(false);
    expect(billAllocationsValid("1000", [{ amount: "10", ref_name: " " }])).toBe(false);
  });
});

describe("applyTds", () => {
  const base = [
    { ledger_id: "purchase", entry_type: "DR" as const, amount: "100000" },
    { ledger_id: "supplier", entry_type: "CR" as const, amount: "100000" },
  ];
  it("reduces the supplier and credits TDS payable", () => {
    const out = applyTds(base, "supplier", "tds", "1000");
    expect(out.find((e) => e.ledger_id === "supplier")?.amount).toBe("99000");
    expect(out.find((e) => e.ledger_id === "tds")).toEqual({ ledger_id: "tds", entry_type: "CR", amount: "1000.00" });
    expect(voucherTotals(out.map((e) => ({ side: e.entry_type, amount: e.amount }))).balanced).toBe(true);
  });
  it("is idempotent and removable", () => {
    const once = applyTds(base, "supplier", "tds", "1000");
    const twice = applyTds(once, "supplier", "tds", "2000");
    expect(twice.find((e) => e.ledger_id === "supplier")?.amount).toBe("98000");
    expect(twice.filter((e) => e.ledger_id === "tds")).toHaveLength(1);
    const removed = applyTds(twice, "supplier", "tds", "0");
    expect(removed).toHaveLength(2);
    expect(removed.find((e) => e.ledger_id === "supplier")?.amount).toBe("100000");
  });
  it("rejects bad input", () => {
    expect(() => applyTds(base, "missing", "tds", "1")).toThrow();
    expect(() => applyTds(base, "supplier", "tds", "200000")).toThrow();
  });
});
