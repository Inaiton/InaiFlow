import { add, cmp, isDecimal, isNegative, isZero, sub, type Decimal } from "@/core/money";

/** Counts entered on a run step. Empty strings mean "not entered" (treated as 0). */
export interface StepCounts {
  input: Decimal;
  accepted: Decimal;
  rejected: Decimal;
  rework: Decimal;
}

export type CountField = keyof StepCounts;

export interface CountsCheck {
  ok: boolean;
  /** input − (accepted + rejected + rework); positive = units still unaccounted for. */
  remaining: Decimal;
  total: Decimal;
  errors: Partial<Record<CountField | "sum", string>>;
  /** A defect description is required when units are rejected. */
  needsDefect: boolean;
}

const v = (s: string): Decimal => (s.trim() === "" ? "0" : s.trim());

/**
 * Live validation for step entry: every count must be a non-negative decimal and
 * accepted + rejected + rework must equal input (server rule QTY_MISMATCH).
 */
export function checkCounts(c: StepCounts): CountsCheck {
  const errors: CountsCheck["errors"] = {};
  const fields: CountField[] = ["input", "accepted", "rejected", "rework"];
  for (const f of fields) {
    const raw = v(c[f]);
    if (!isDecimal(raw)) errors[f] = "Enter a number (up to 4 decimals)";
    else if (isNegative(raw)) errors[f] = "Can’t be negative";
  }
  if (Object.keys(errors).length > 0) return { ok: false, remaining: "0", total: "0", errors, needsDefect: false };
  const total = add(v(c.accepted), v(c.rejected), v(c.rework));
  const remaining = sub(v(c.input), total);
  if (isZero(v(c.input))) errors.input = "Input must be more than zero";
  const diff = cmp(total, v(c.input));
  if (diff > 0) errors.sum = `That’s ${sub(total, v(c.input))} more than the input`;
  else if (diff < 0) errors.sum = `${remaining} units are not counted yet`;
  return { ok: Object.keys(errors).length === 0, remaining, total, errors, needsDefect: cmp(v(c.rejected), "0") > 0 };
}

/** "Fill the rest as accepted" helper: accepted = input − rejected − rework (never below 0). */
export function acceptRemainder(c: StepCounts): StepCounts {
  const rest = sub(v(c.input), add(v(c.rejected), v(c.rework)));
  return { ...c, accepted: isNegative(rest) ? "0" : rest };
}
