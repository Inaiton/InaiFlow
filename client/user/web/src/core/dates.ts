import { addMonths, format, isValid, parseISO, startOfMonth } from "date-fns";

/** ISO date `YYYY-MM-DD` (local calendar date, no timezone shift). */
export type IsoDate = string;
/** Month key `YYYY-MM`. */
export type MonthKey = string;

export interface FinancialYear {
  label: string;
  start: IsoDate;
  end: IsoDate;
}

const pad = (n: number) => String(n).padStart(2, "0");

export function toIsoDate(d: Date): IsoDate {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

export function parseIsoDate(s: IsoDate): Date {
  const [y, m, d] = s.split("-").map(Number);
  return new Date(y ?? 1970, (m ?? 1) - 1, d ?? 1);
}

export const todayIso = (): IsoDate => toIsoDate(new Date());

/** Financial year containing `date`; `startMonth` is 1-based (India: April = 4). */
export function fyForDate(date: Date | IsoDate, startMonth = 4): FinancialYear {
  const d = typeof date === "string" ? parseIsoDate(date) : date;
  const startYear = d.getMonth() + 1 >= startMonth ? d.getFullYear() : d.getFullYear() - 1;
  const start = new Date(startYear, startMonth - 1, 1);
  const end = new Date(startYear + 1, startMonth - 1, 0);
  const endYear = end.getFullYear();
  const label = startMonth === 1 ? `FY ${startYear}` : `FY ${startYear}-${String(endYear).slice(-2)}`;
  return { label, start: toIsoDate(start), end: toIsoDate(end) };
}

export const monthKey = (d: Date | IsoDate): MonthKey => (typeof d === "string" ? d.slice(0, 7) : format(d, "yyyy-MM"));
export const monthStart = (m: MonthKey): IsoDate => `${m}-01`;

/** Months (`YYYY-MM`) of a financial year, in order. */
export function monthsOfFy(fy: Pick<FinancialYear, "start">): MonthKey[] {
  const first = startOfMonth(parseIsoDate(fy.start));
  return Array.from({ length: 12 }, (_, i) => monthKey(addMonths(first, i)));
}

/** "Sept 2026"-style label matching the document vault naming. */
export function monthLabel(m: MonthKey): string {
  const d = parseIsoDate(monthStart(m));
  const name = format(d, "MMM");
  return `${name === "Sep" ? "Sept" : name} ${d.getFullYear()}`;
}

export function formatDate(value: IsoDate | string | null | undefined, pattern = "dd MMM yyyy"): string {
  if (!value) return "—";
  const d = value.length === 10 ? parseIsoDate(value) : parseISO(value);
  return isValid(d) ? format(d, pattern) : "—";
}

export const formatDateTime = (value: string | null | undefined): string => formatDate(value, "dd MMM yyyy, h:mm a");

/** FY progress (0–100) for the sidebar meter. */
export function fyProgress(fy: Pick<FinancialYear, "start" | "end">, now = new Date()): number {
  const s = parseIsoDate(fy.start).getTime();
  const e = parseIsoDate(fy.end).getTime();
  if (now.getTime() <= s) return 0;
  if (now.getTime() >= e) return 100;
  return Math.round(((now.getTime() - s) / (e - s)) * 100);
}
