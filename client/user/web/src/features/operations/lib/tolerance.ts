import type { Schemas } from "@/core/api/types";
import { add, cmp, isDecimal, sub, type Decimal } from "@/core/money";

export type QcField = Schemas["QcField"];

export interface Limits {
  lower: Decimal | null;
  upper: Decimal | null;
}

const isNum = (f: QcField) => (f.type ?? "NUMBER").toUpperCase() === "NUMBER";

/** Lower/upper acceptance limits for a numeric field (null when no tolerance is defined). */
export function limits(f: QcField): Limits | null {
  if (!isNum(f) || !f.nominal || !isDecimal(f.nominal)) return null;
  const lower = f.tol_minus && isDecimal(f.tol_minus) ? sub(f.nominal, f.tol_minus) : null;
  const upper = f.tol_plus && isDecimal(f.tol_plus) ? add(f.nominal, f.tol_plus) : null;
  if (lower === null && upper === null) return null;
  return { lower, upper };
}

/** "40 ± 0.02 mm", "40 −0.01 / +0.03 mm", "Yes / No", "One of: A, B". */
export function toleranceHint(f: QcField): string {
  const unit = f.unit ? ` ${f.unit}` : "";
  const type = (f.type ?? "NUMBER").toUpperCase();
  if (type === "BOOL") return "Yes / No";
  if (f.options && f.options.length) return `One of: ${f.options.join(", ")}`;
  if (!isNum(f) || !f.nominal) return type === "TEXT" ? "Text" : "—";
  const m = f.tol_minus ?? null;
  const p = f.tol_plus ?? null;
  if (m && p && cmp(m, p) === 0) return `${f.nominal} ± ${p}${unit}`;
  if (m || p) return `${f.nominal} −${m ?? "0"} / +${p ?? "0"}${unit}`;
  return `${f.nominal}${unit}`;
}

const TRUE = ["true", "yes", "y", "1", "ok", "pass"];
const FALSE = ["false", "no", "n", "0", "not ok", "fail"];

/**
 * In / out of tolerance for one reading. Returns null when there is nothing to judge
 * (empty value, free text, or a numeric field without tolerances).
 */
export function evaluateReading(f: QcField, value: string | null | undefined): boolean | null {
  const raw = (value ?? "").trim();
  if (raw === "") return null;
  const type = (f.type ?? "NUMBER").toUpperCase();
  if (type === "BOOL") {
    const s = raw.toLowerCase();
    if (TRUE.includes(s)) return true;
    if (FALSE.includes(s)) return false;
    return null;
  }
  if (f.options && f.options.length) return f.options.includes(raw);
  if (!isNum(f)) return null;
  if (!isDecimal(raw)) return false;
  const lim = limits(f);
  if (!lim) return null;
  if (lim.lower !== null && cmp(raw, lim.lower) < 0) return false;
  if (lim.upper !== null && cmp(raw, lim.upper) > 0) return false;
  return true;
}

export interface FilledReading {
  value: string;
  autoFilled: boolean;
}

/**
 * Quick QC: every field with a nominal and no entered value is filled with the nominal,
 * flagged `autoFilled` (server applies the same rule and tags "Auto · nominal").
 */
export function quickQcAutofill(fields: QcField[], current: Record<string, string>): Record<string, FilledReading> {
  const out: Record<string, FilledReading> = {};
  for (const f of fields) {
    const entered = (current[f.key] ?? "").trim();
    if (entered !== "") out[f.key] = { value: entered, autoFilled: false };
    else if (f.nominal) out[f.key] = { value: f.nominal, autoFilled: true };
    else out[f.key] = { value: "", autoFilled: false };
  }
  return out;
}

/** Required fields left empty (for fields without a nominal Quick QC cannot fill them). */
export function missingRequired(fields: QcField[], values: Record<string, string>, quick: boolean): QcField[] {
  return fields.filter((f) => f.required && (values[f.key] ?? "").trim() === "" && !(quick && f.nominal));
}

export function countOutOfTolerance(fields: QcField[], values: Record<string, string>): number {
  return fields.filter((f) => evaluateReading(f, values[f.key]) === false).length;
}
