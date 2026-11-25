import { describe, expect, it } from "vitest";
import { kindOf } from "../../lib/voucher-kinds";
import { defaultPartyBills, entriesBalanced, toComputeTaxIn, toVoucherIn, validateDraft } from "./build";
import { draftReducer, emptyDraft, type Draft } from "./draft";

const journal = kindOf("JOURNAL")!;
const sales = kindOf("SALES")!;
const sj = kindOf("STOCK_JOURNAL")!;
const so = kindOf("SALES_ORDER")!;

function filledJournal(): Draft {
  let d = emptyDraft("JOURNAL", "vt", "2026-11-23");
  const [a, b] = d.acc;
  d = draftReducer(d, { type: "acc", key: a!.key, patch: { ledger_id: "dep", amount: "86400" } });
  d = draftReducer(d, { type: "acc-commit", key: a!.key });
  d = draftReducer(d, { type: "acc", key: b!.key, patch: { ledger_id: "accdep", amount: "86400" } });
  return d;
}

describe("draft reducer", () => {
  it("adds a pre-filled balancing line after the last line", () => {
    let d = emptyDraft("JOURNAL", "vt", "2026-11-23");
    d = draftReducer(d, { type: "acc-remove", key: d.acc[1]!.key });
    const k = d.acc[0]!.key;
    d = draftReducer(d, { type: "acc", key: k, patch: { ledger_id: "x", amount: "500" } });
    d = draftReducer(d, { type: "acc-commit", key: k });
    expect(d.acc).toHaveLength(2);
    expect(d.acc[1]).toMatchObject({ side: "CR", amount: "500" });
    // balanced → no extra line
    d = draftReducer(d, { type: "acc", key: d.acc[1]!.key, patch: { ledger_id: "y" } });
    d = draftReducer(d, { type: "acc-commit", key: d.acc[1]!.key });
    expect(d.acc).toHaveLength(2);
  });
  it("recomputes item amounts from qty × rate − disc", () => {
    let d = emptyDraft("SALES", "vt", "2026-11-23", "g1");
    const k = d.items[0]!.key;
    d = draftReducer(d, { type: "item", key: k, patch: { qty: "20", rate: "1425" } });
    d = draftReducer(d, { type: "item", key: k, patch: { disc: "2" } });
    expect(d.items[0]!.amount).toBe("27930.00");
    expect(d.items[0]!.godown_id).toBe("g1");
  });
  it("keeps at least one item row", () => {
    const d = emptyDraft("SALES", "vt", "2026-11-23");
    expect(draftReducer(d, { type: "item-remove", key: d.items[0]!.key }).items).toHaveLength(1);
  });
});

describe("toVoucherIn", () => {
  it("builds a balanced journal", () => {
    const d = filledJournal();
    expect(validateDraft(d, journal, undefined)).toEqual([]);
    const v = toVoucherIn(d, { kind: journal });
    expect(v.entries).toHaveLength(2);
    expect(v.entries[0]).toMatchObject({ ledger_id: "dep", entry_type: "DR", amount: "86400.00" });
    expect(entriesBalanced(v.entries)).toBe(true);
  });
  it("rejects an unbalanced journal", () => {
    let d = filledJournal();
    d = draftReducer(d, { type: "acc", key: d.acc[1]!.key, patch: { amount: "100" } });
    expect(validateDraft(d, journal, undefined)).toContain("Debit and credit totals must match");
  });
  it("builds a sales invoice from suggested entries with bill-wise party and TDS-free", () => {
    let d = emptyDraft("SALES", "vt", "2026-11-23", "fg");
    d = draftReducer(d, { type: "set", patch: { party_ledger_id: "party", ledger_id: "sales", party_bill_wise: true } });
    d = draftReducer(d, { type: "item", key: d.items[0]!.key, patch: { stock_item_id: "item", qty: "10", rate: "100", gst_rate: "18" } });
    const req = toComputeTaxIn(d);
    expect(req?.lines[0]).toMatchObject({ ledger_id: "sales", stock_item_id: "item", amount: "1000.00", gst_rate: "18" });
    const tax = {
      tax_split: "CGST_SGST", taxable_total: "1000", cgst: "90", sgst: "90", igst: "0", cess: "0", round_off: "0", invoice_total: "1180", breakup: [], warnings: [],
      suggested_entries: [
        { ledger_id: "party", entry_type: "DR" as const, amount: "1180" },
        { ledger_id: "sales", entry_type: "CR" as const, amount: "1000" },
        { ledger_id: "cgst", entry_type: "CR" as const, amount: "90" },
        { ledger_id: "sgst", entry_type: "CR" as const, amount: "90" },
      ],
    };
    expect(validateDraft(d, sales, tax)).toEqual([]);
    const v = toVoucherIn(d, { kind: sales, tax, partyBills: (amt) => defaultPartyBills(d, amt, "SI/0007", 30) });
    expect(v.party_ledger_id).toBe("party");
    expect(v.inventory?.[0]).toMatchObject({ movement_type: "OUTWARD", godown_id: "fg", quantity: "10" });
    expect(v.entries[0]?.bill_allocations).toEqual([{ ref_type: "NEW_REF", ref_name: "SI/0007", amount: "1180", due_date: "2026-12-23" }]);
    expect(entriesBalanced(v.entries)).toBe(true);
  });
  it("applies TDS on a purchase", () => {
    let d = emptyDraft("PURCHASE", "vt", "2026-11-23", "rm");
    d = draftReducer(d, { type: "set", patch: { party_ledger_id: "sup", ledger_id: "pur", tds: { section: "194C", amount: "100", ledger_id: "tds" } } });
    const tax = { tax_split: "", taxable_total: "10000", cgst: "0", sgst: "0", igst: "0", cess: "0", round_off: "0", invoice_total: "10000", breakup: [], warnings: [],
      suggested_entries: [{ ledger_id: "pur", entry_type: "DR" as const, amount: "10000" }, { ledger_id: "sup", entry_type: "CR" as const, amount: "10000" }] };
    const v = toVoucherIn(d, { kind: kindOf("PURCHASE")!, tax });
    expect(v.entries.find((e) => e.ledger_id === "sup")?.amount).toBe("9900");
    expect(entriesBalanced(v.entries)).toBe(true);
  });
  it("orders and stock journals carry no entries", () => {
    let d = emptyDraft("SALES_ORDER", "vt", "2026-11-23", "fg");
    d = draftReducer(d, { type: "set", patch: { party_ledger_id: "party" } });
    d = draftReducer(d, { type: "item", key: d.items[0]!.key, patch: { stock_item_id: "i", qty: "5", rate: "10" } });
    expect(validateDraft(d, so, undefined)).toEqual([]);
    expect(toVoucherIn(d, { kind: so }).entries).toEqual([]);
    let s = emptyDraft("STOCK_JOURNAL", "vt", "2026-11-23", "main");
    s = draftReducer(s, { type: "inv", key: s.inv[0]!.key, patch: { stock_item_id: "rm", qty: "4", rate: "25" } });
    s = draftReducer(s, { type: "inv-remove", key: s.inv[1]!.key });
    const sv = toVoucherIn(s, { kind: sj });
    expect(sv.entries).toEqual([]);
    expect(sv.inventory).toEqual([{ stock_item_id: "rm", godown_id: "main", movement_type: "OUTWARD", quantity: "4", rate: "25", amount: "100.00", batch_number: null }]);
  });
});
