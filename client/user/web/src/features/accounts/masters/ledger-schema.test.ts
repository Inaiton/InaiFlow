import { describe, expect, it } from "vitest";
import { emptyLedger, fromLedger, ledgerSchema, partsFromGstin, toLedgerIn } from "./ledger-schema";

describe("ledger schema", () => {
  it("validates GSTIN/PAN/IFSC", () => {
    const bad = ledgerSchema.safeParse({ ...emptyLedger("g"), name: "X", gstin: "33ABC", pan: "abc", ifsc: "HDFC1" });
    expect(bad.success).toBe(false);
    const ok = ledgerSchema.safeParse({ ...emptyLedger("g"), name: "Lakshmi", gstin: "33aaffl3021c1zk", ifsc: "hdfc0001234" });
    expect(ok.success && ok.data.gstin).toBe("33AAFFL3021C1ZK");
  });
  it("maps to LedgerIn and back", () => {
    const v = ledgerSchema.parse({ ...emptyLedger("g"), name: "Lakshmi", gstin: "33AAFFL3021C1ZK", state_code: "33", credit_limit: "800000", default_credit_days: "45", maintain_bill_by_bill: true });
    const body = toLedgerIn(v, "party");
    expect(body.party_details?.gstin).toBe("33AAFFL3021C1ZK");
    expect(body.default_credit_days).toBe(45);
    expect(body.opening_balance).toBe("0");
    expect(body.tax_config).toBeNull();
    const plain = toLedgerIn(ledgerSchema.parse({ ...emptyLedger("g"), name: "Rent" }), "other");
    expect(plain.party_details).toBeNull();
    const tax = toLedgerIn(ledgerSchema.parse({ ...emptyLedger("g"), name: "Output CGST", tax_type: "GST", gst_head: "CGST" }), "tax");
    expect(tax.tax_config).toEqual({ tax_type: "GST", gst_head: "CGST", rate: null, tds_section: null });
  });
  it("derives state and PAN from GSTIN", () => {
    expect(partsFromGstin("33AAKCA4821M1Z6")).toEqual({ state_code: "33", pan: "AAKCA4821M" });
    expect(partsFromGstin("bad")).toBeNull();
  });
  it("reads a ledger for editing", () => {
    const f = fromLedger({
      id: "1", group_id: "g", group_name: "Sundry Debtors", nature: "ASSETS", name: "A", alias: null, system_code: null, currency_code: "INR",
      opening_balance: "0", opening_balance_type: "DR", maintain_bill_by_bill: true, default_credit_days: 30, credit_limit: null, party_details: { gstin: "33AAKCA4821M1Z6" },
      tax_config: null, interest_config: null, is_active: true, closing_balance: "0", closing_balance_type: "DR", created_at: "2026-01-01T00:00:00Z",
    });
    expect(f.default_credit_days).toBe("30");
    expect(f.gstin).toBe("33AAKCA4821M1Z6");
  });
});
