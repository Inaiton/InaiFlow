import { formatDate } from "@/core/dates";
import { abs, formatMoney, formatQty, isNegative, isZero, toScaled, type Decimal } from "@/core/money";
import type { Schemas } from "@/core/api/types";

export type DrCr = Schemas["DrCr"];

/** "12,34,567.00" — Indian grouping, no symbol (Tally style for tables). */
export const amt = (v: Decimal | null | undefined, decimals = 2): string => formatMoney(v ?? "0", { symbol: false, decimals });
/** "₹12,34,567.00" */
export const inr = (v: Decimal | null | undefined, decimals = 2): string => formatMoney(v ?? "0", { decimals });
/** Blank for zero (Tally leaves empty Dr/Cr cells). */
export const amtOrBlank = (v: Decimal | null | undefined): string => (isZero(v) ? "" : amt(v));
export const qty = (v: Decimal | null | undefined): string => formatQty(v ?? "0");

/** Balance with Dr/Cr suffix: `drcr("6428", "DR")` → "6,428.00 Dr". Zero → "0.00". */
export function drcr(value: Decimal | null | undefined, type: DrCr | null | undefined, opts: { symbol?: boolean } = {}): string {
  const v = value ?? "0";
  const body = opts.symbol ? inr(abs(v)) : amt(abs(v));
  if (isZero(v)) return body;
  // a negative amount flips the side
  const side = isNegative(v) ? (type === "DR" ? "CR" : "DR") : type;
  return `${body} ${side === "CR" ? "Cr" : "Dr"}`;
}

/** Signed decimal (positive = Dr) → "1,200.00 Dr" / "1,200.00 Cr". */
export const signedDrCr = (v: Decimal | null | undefined, opts: { symbol?: boolean } = {}): string =>
  drcr(abs(v ?? "0"), isNegative(v ?? "0") ? "CR" : "DR", opts);

/** Dates in accounts screens: dd-MMM-yyyy (e.g. 23-Nov-2026). */
export const accDate = (v: string | null | undefined): string => formatDate(v, "dd-MMM-yyyy");
/** Short Tally style: 1-Apr-26 */
export const shortDate = (v: string | null | undefined): string => formatDate(v, "d-MMM-yy");

/** "SALES_ORDER" → "Sales order" */
export const humanize = (s: string | null | undefined): string => {
  if (!s) return "—";
  const t = s.replace(/_/g, " ").toLowerCase();
  return t.charAt(0).toUpperCase() + t.slice(1);
};

/** Integer percentage a/b (0 when b is 0) — BigInt maths, for meters only. */
export function percentOf(a: Decimal | null | undefined, b: Decimal | null | undefined): number {
  const d = toScaled(b ?? "0");
  if (d === 0n) return 0;
  return Number((toScaled(a ?? "0") * 100n) / d);
}
