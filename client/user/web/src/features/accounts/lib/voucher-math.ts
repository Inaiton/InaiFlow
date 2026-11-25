import { add, cmp, isZero, mul, neg, round, sub, sum, toScaled, abs, type Decimal } from "@/core/money";
import type { Schemas } from "@/core/api/types";
import type { DrCr } from "./format";

export type EntryIn = Schemas["EntryIn"];
export type BillAllocation = Schemas["BillAllocation"];

export interface DrCrLine {
  side: DrCr;
  amount: Decimal | null | undefined;
}

export interface VoucherTotals {
  debit: Decimal;
  credit: Decimal;
  /** debit − credit */
  difference: Decimal;
  balanced: boolean;
}

const safe = (v: Decimal | null | undefined): Decimal => (v && /^-?\d+(\.\d+)?$/.test(v) ? v : "0");

/** ΣDr, ΣCr and whether the voucher balances (non-zero and equal). */
export function voucherTotals(lines: DrCrLine[]): VoucherTotals {
  const debit = sum(lines.filter((l) => l.side === "DR").map((l) => safe(l.amount)));
  const credit = sum(lines.filter((l) => l.side === "CR").map((l) => safe(l.amount)));
  const difference = sub(debit, credit);
  return { debit, credit, difference, balanced: isZero(difference) && !isZero(debit) };
}

/** Tally pre-fills the next line with the amount that balances the voucher. */
export function balancingLine(lines: DrCrLine[]): { side: DrCr; amount: Decimal } | null {
  const { difference } = voucherTotals(lines);
  if (isZero(difference)) return null;
  return toScaled(difference) > 0n ? { side: "CR", amount: difference } : { side: "DR", amount: neg(difference) };
}

/** Invoice line amount = qty × rate × (1 − disc%), rounded to paise. Empty inputs count as 0. */
export function lineAmount(qty: Decimal | null | undefined, rate: Decimal | null | undefined, discPct?: Decimal | null): Decimal {
  const gross = mul(safe(qty), safe(rate));
  const d = safe(discPct ?? "0");
  if (isZero(d)) return round(gross, 2);
  const net = sub(gross, mul(gross, mul(d, "0.01")));
  return round(net, 2);
}

/** Taxable subtotal of invoice rows. */
export const invoiceSubtotal = (rows: { amount: Decimal | null | undefined }[]): Decimal => round(sum(rows.map((r) => safe(r.amount))), 2);

/** Amount still unallocated on a bill-wise entry (entry amount − Σ allocations). */
export function billRemaining(entryAmount: Decimal | null | undefined, allocations: { amount: Decimal | null | undefined }[]): Decimal {
  return sub(safe(entryAmount), sum(allocations.map((a) => safe(a.amount))));
}

/** Bill allocations are valid when every amount is > 0 and Σ ≤ entry amount (plan §3.8). */
export function billAllocationsValid(entryAmount: Decimal | null | undefined, allocations: { amount: Decimal | null | undefined; ref_name: string }[]): boolean {
  if (allocations.some((a) => !a.ref_name.trim() || cmp(safe(a.amount), "0") <= 0)) return false;
  return cmp(billRemaining(entryAmount, allocations), "0") >= 0;
}

/**
 * Apply a TDS deduction to balanced entries: reduce the CR line of `adjustLedgerId` (supplier on a purchase, bank/cash on a
 * payment) and add `CR tdsLedgerId`. Any earlier line on the TDS ledger is folded back first, so re-applying is idempotent.
 */
export function applyTds(entries: EntryIn[], adjustLedgerId: string, tdsLedgerId: string, tdsAmount: Decimal): EntryIn[] {
  let list = entries.map((e) => ({ ...e }));
  const prev = list.filter((e) => e.ledger_id === tdsLedgerId && e.entry_type === "CR");
  list = list.filter((e) => !(e.ledger_id === tdsLedgerId && e.entry_type === "CR"));
  const target = list.find((e) => e.ledger_id === adjustLedgerId && e.entry_type === "CR");
  if (!target) throw new Error("No credit line to deduct TDS from");
  target.amount = add(target.amount, ...prev.map((p) => p.amount));
  if (isZero(tdsAmount)) return list;
  if (cmp(tdsAmount, target.amount) > 0) throw new Error("TDS exceeds the amount payable");
  target.amount = sub(target.amount, tdsAmount);
  return [...list, { ledger_id: tdsLedgerId, entry_type: "CR", amount: round(tdsAmount, 2) }];
}

/** Absolute difference for display. */
export const absDiff = (t: VoucherTotals): Decimal => abs(t.difference);
