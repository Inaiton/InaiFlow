import { addDays, format } from "date-fns";
import { parseIsoDate, toIsoDate, type IsoDate } from "@/core/dates";

export interface Period {
  from: IsoDate;
  to: IsoDate;
}

const ISO = /^\d{4}-\d{2}-\d{2}$/;

/** Default report period: FY start → today (clamped to the FY end). */
export function defaultPeriod(fy: { start: IsoDate; end: IsoDate }, today: IsoDate): Period {
  const to = today < fy.start ? fy.end : today > fy.end ? fy.end : today;
  return { from: fy.start, to };
}

/** Read `?from=&to=` with a fallback; invalid or reversed ranges fall back. */
export function periodFromParams(params: { get(name: string): string | null }, fallback: Period): Period {
  const from = params.get("from");
  const to = params.get("to");
  if (!from || !to || !ISO.test(from) || !ISO.test(to) || from > to) return fallback;
  return { from, to };
}

/** "1-Apr-26 to 31-Mar-27" */
export const periodLabel = (p: Period): string => `${format(parseIsoDate(p.from), "d-MMM-yy")} to ${format(parseIsoDate(p.to), "d-MMM-yy")}`;

/** Month key "YYYY-MM" → { from: 1st, to: last day }. */
export function monthPeriod(month: string): Period {
  const [y, m] = month.split("-").map(Number);
  const first = new Date(y ?? 1970, (m ?? 1) - 1, 1);
  const last = addDays(new Date(y ?? 1970, m ?? 1, 1), -1);
  return { from: toIsoDate(first), to: toIsoDate(last) };
}

/** Indian FY quarter label for TDS returns: "2026-Q3" style key → months. */
export function fyQuarters(fyStart: IsoDate): { key: string; label: string }[] {
  const y = Number(fyStart.slice(0, 4));
  return [
    { key: `${y}-Q1`, label: `Q1 · Apr–Jun ${y}` },
    { key: `${y}-Q2`, label: `Q2 · Jul–Sep ${y}` },
    { key: `${y}-Q3`, label: `Q3 · Oct–Dec ${y}` },
    { key: `${y}-Q4`, label: `Q4 · Jan–Mar ${y + 1}` },
  ];
}
