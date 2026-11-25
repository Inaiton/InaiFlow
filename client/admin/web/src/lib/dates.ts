import { format, formatDistanceToNowStrict, isValid, parseISO } from "date-fns";

function toDate(v: string | null | undefined): Date | null {
  if (!v) return null;
  const d = parseISO(v);
  return isValid(d) ? d : null;
}

export function fmtDate(v: string | null | undefined): string {
  const d = toDate(v);
  return d ? format(d, "dd MMM yyyy") : "—";
}

export function fmtDateTime(v: string | null | undefined): string {
  const d = toDate(v);
  return d ? format(d, "dd MMM yyyy, HH:mm") : "—";
}

export function fmtRelative(v: string | null | undefined): string {
  const d = toDate(v);
  return d ? `${formatDistanceToNowStrict(d)} ${d.getTime() > Date.now() ? "from now" : "ago"}` : "—";
}

export function todayISO(): string {
  return format(new Date(), "yyyy-MM-dd");
}
