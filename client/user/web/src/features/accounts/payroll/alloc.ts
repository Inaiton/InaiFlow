import { cmp, isDecimal, sum } from "@/core/money";

/** Run allocations must be empty or total exactly 100% with every share > 0 and no duplicate run. */
export function allocationError(rows: { period_run_id: string; share_pct: string }[]): string | null {
  if (rows.length === 0) return null;
  if (rows.some((r) => !r.period_run_id)) return "Pick a period run on every line";
  if (new Set(rows.map((r) => r.period_run_id)).size !== rows.length) return "Each run only once";
  if (rows.some((r) => !isDecimal(r.share_pct) || cmp(r.share_pct, "0") <= 0)) return "Shares must be positive";
  return cmp(sum(rows.map((r) => r.share_pct)), "100") === 0 ? null : "Shares must total 100%";
}
