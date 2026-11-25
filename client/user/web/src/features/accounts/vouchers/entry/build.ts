import type { Schemas } from "@/core/api/types";
import { cmp, isZero, round } from "@/core/money";
import type { VoucherKind } from "../../lib/voucher-kinds";
import { applyTds, billAllocationsValid, voucherTotals, type EntryIn } from "../../lib/voucher-math";
import { accTotals, type Draft } from "./draft";

type VoucherIn = Schemas["VoucherIn"];
type ComputeTaxIn = Schemas["ComputeTaxIn"];
type ComputeTaxOut = Schemas["ComputeTaxOut"];

const positive = (v: string) => Boolean(v) && cmp(v, "0") > 0;

/** Invoice lines → compute-tax request (null until party, ledger and one priced line exist). */
export function toComputeTaxIn(d: Draft): ComputeTaxIn | null {
  if (!d.party_ledger_id || !d.ledger_id) return null;
  const lines: Schemas["TaxLineIn"][] = [];
  for (const r of d.items) {
    if (!positive(r.amount)) continue;
    if (r.kind === "item" && r.stock_item_id)
      lines.push({ ledger_id: d.ledger_id, stock_item_id: r.stock_item_id, quantity: r.qty || null, rate: r.rate || null, amount: round(r.amount, 2), gst_rate: r.gst_rate || null, hsn_sac_code: r.hsn || null });
    else if (r.kind === "ledger" && r.ledger_id) lines.push({ ledger_id: r.ledger_id, amount: round(r.amount, 2), gst_rate: r.gst_rate || null, hsn_sac_code: r.hsn || null });
  }
  if (lines.length === 0) return null;
  return { voucher_type_id: d.voucher_type_id, voucher_date: d.date, party_ledger_id: d.party_ledger_id, lines, gst: gstOf(d) };
}

const gstOf = (d: Draft): Schemas["GstIn"] => ({ place_of_supply_state_code: d.pos_state || null, reverse_charge: d.reverse_charge, is_export: d.is_export, is_sez: d.is_sez });

/** Validation messages shown above Accept; empty = ready to save. */
export function validateDraft(d: Draft, kind: VoucherKind, tax: ComputeTaxOut | undefined): string[] {
  const errs: string[] = [];
  if (!d.voucher_type_id) errs.push("Choose a voucher type");
  if (!d.date) errs.push("Enter the voucher date");
  if (kind.mode === "accounting") {
    const lines = d.acc.filter((r) => r.ledger_id && positive(r.amount));
    if (lines.length < 2) errs.push("Enter at least one Dr and one Cr line");
    const t = accTotals(d);
    if (!t.balanced) errs.push("Debit and credit totals must match");
    for (const r of lines) if (r.bill_wise && r.bills.length > 0 && !billAllocationsValid(r.amount, r.bills)) errs.push("Bill allocations exceed the line amount");
  } else if (kind.mode === "invoice") {
    if (!d.party_ledger_id) errs.push("Choose the party ledger");
    if (!kind.order && !d.ledger_id) errs.push(`Choose the ${kind.ledgerKind === "sales" ? "sales" : "purchase"} ledger`);
    const priced = d.items.filter((r) => positive(r.amount) && (r.stock_item_id || r.ledger_id));
    if (priced.length === 0) errs.push("Add at least one item line with an amount");
    if (d.items.some((r) => r.kind === "item" && r.stock_item_id && positive(r.qty) && !r.godown_id)) errs.push("Choose a godown for every item");
    if (!kind.order && !tax) errs.push("Tax is still being calculated");
  } else {
    const lines = d.inv.filter((r) => r.stock_item_id);
    if (lines.length === 0) errs.push("Add at least one stock line");
    if (lines.some((r) => !r.godown_id || !positive(r.qty))) errs.push("Every stock line needs a godown and quantity");
  }
  return errs;
}

function accountingEntries(d: Draft): EntryIn[] {
  return d.acc
    .filter((r) => r.ledger_id && positive(r.amount))
    .map((r) => ({
      ledger_id: r.ledger_id!, entry_type: r.side, amount: round(r.amount, 2), cost_centre_id: r.cost_centre_id,
      bill_allocations: r.bill_wise ? r.bills : [], instrument_no: r.instrument_no || null, instrument_date: r.instrument_date || null,
    }));
}

/** Party bill reference default: supplier bill no. on purchases, else the expected voucher number. */
export function defaultPartyBills(d: Draft, partyAmount: string, expectedNumber: string, dueDays: number | null): Schemas["BillAllocation"][] {
  if (d.party_bills.length > 0) return d.party_bills;
  const due = dueDays && d.date ? addDays(d.date, dueDays) : null;
  return [{ ref_type: "NEW_REF", ref_name: d.supplier_invoice_no || expectedNumber, amount: partyAmount, due_date: due }];
}

function addDays(iso: string, days: number): string {
  const [y, m, dd] = iso.split("-").map(Number);
  const dt = new Date(Date.UTC(y ?? 1970, (m ?? 1) - 1, (dd ?? 1) + days));
  return dt.toISOString().slice(0, 10);
}

function invoiceEntries(d: Draft, tax: ComputeTaxOut, partyBills: (amount: string) => Schemas["BillAllocation"][] | null): EntryIn[] {
  let entries: EntryIn[] = tax.suggested_entries.map((e) => ({ ...e }));
  if (d.tds && d.party_ledger_id && !isZero(d.tds.amount || "0")) entries = applyTds(entries, d.party_ledger_id, d.tds.ledger_id, d.tds.amount);
  if (d.party_bill_wise) {
    entries = entries.map((e) => (e.ledger_id === d.party_ledger_id ? { ...e, bill_allocations: partyBills(e.amount) ?? [] } : e));
  }
  return entries;
}

export interface BuildContext {
  kind: VoucherKind;
  tax?: ComputeTaxOut;
  editReason?: string;
  attachmentIds?: string[];
  partyBills?: (amount: string) => Schemas["BillAllocation"][] | null;
}

/** Draft → VoucherIn. Orders and stock journals carry no ledger entries. */
export function toVoucherIn(d: Draft, ctx: BuildContext): VoucherIn {
  const { kind } = ctx;
  const base: VoucherIn = {
    voucher_type_id: d.voucher_type_id, voucher_date: d.date, status: d.status, narration: d.narration.trim() || null,
    linked_period_run_id: d.linked_period_run_id, entries: [], edit_reason: ctx.editReason ?? null,
    ...(ctx.attachmentIds ? { attachment_document_ids: ctx.attachmentIds } : {}),
  };
  if (kind.mode === "accounting") return { ...base, entries: accountingEntries(d) };
  if (kind.mode === "inventory") {
    return {
      ...base,
      inventory: d.inv.filter((r) => r.stock_item_id && positive(r.qty)).map((r) => ({
        stock_item_id: r.stock_item_id!, godown_id: r.godown_id, movement_type: r.dir, quantity: r.qty, rate: r.rate || "0", amount: round(r.amount || "0", 2), batch_number: r.batch || null,
      })),
    };
  }
  const inventory = d.items.filter((r) => r.kind === "item" && r.stock_item_id && positive(r.qty)).map((r) => ({
    stock_item_id: r.stock_item_id!, godown_id: r.godown_id, movement_type: kind.movement ?? "OUTWARD", quantity: r.qty, rate: r.rate || "0",
    amount: round(r.amount || "0", 2), batch_number: r.batch || null, gst_rate: r.gst_rate || null,
  }));
  const inv: VoucherIn = {
    ...base, party_ledger_id: d.party_ledger_id, supplier_invoice_no: d.supplier_invoice_no || null, supplier_invoice_date: d.supplier_invoice_date || null,
    inventory, gst: gstOf(d),
  };
  if (kind.order || !ctx.tax) return inv;
  return { ...inv, entries: invoiceEntries(d, ctx.tax, ctx.partyBills ?? (() => null)) };
}

/** Totals check of built entries (defensive: never submit an unbalanced voucher). */
export const entriesBalanced = (entries: EntryIn[]) => voucherTotals(entries.map((e) => ({ side: e.entry_type, amount: e.amount }))).balanced;
