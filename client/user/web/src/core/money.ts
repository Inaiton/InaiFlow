/**
 * Decimal money/quantity helpers. The API exchanges decimals as strings matching
 * `^-?\d+(\.\d{1,4})?$` (plan §3.1). All math here uses BigInt scaled by 10^4 — never floats.
 */
export const SCALE = 4;
const FACTOR = 10n ** BigInt(SCALE);
const DECIMAL_RE = /^-?\d+(\.\d+)?$/;

export type Decimal = string;

function roundHalfUp(n: bigint, divisor: bigint): bigint {
  if (divisor === 1n) return n;
  const neg = n < 0n;
  const abs = neg ? -n : n;
  const q = abs / divisor;
  const r = abs % divisor;
  const rounded = r * 2n >= divisor ? q + 1n : q;
  return neg ? -rounded : rounded;
}

/** Parse a canonical decimal string into a scaled BigInt (rounds half-up beyond 4 dp). */
export function toScaled(value: Decimal | number | null | undefined): bigint {
  if (value === null || value === undefined || value === "") return 0n;
  const s = typeof value === "number" ? String(value) : value.trim();
  if (!DECIMAL_RE.test(s)) throw new Error(`Invalid decimal: ${s}`);
  const neg = s.startsWith("-");
  const body = neg ? s.slice(1) : s;
  const [intPart = "0", fracRaw = ""] = body.split(".");
  let scaled: bigint;
  if (fracRaw.length <= SCALE) {
    scaled = BigInt(intPart) * FACTOR + BigInt(fracRaw.padEnd(SCALE, "0") || "0");
  } else {
    const extra = fracRaw.length - SCALE;
    const full = BigInt(intPart + fracRaw);
    scaled = roundHalfUp(full, 10n ** BigInt(extra));
  }
  return neg ? -scaled : scaled;
}

/** Scaled BigInt → canonical API string (trailing zeros trimmed, no exponent). */
export function fromScaled(n: bigint, minDecimals = 0): Decimal {
  const neg = n < 0n;
  const abs = neg ? -n : n;
  const int = abs / FACTOR;
  let frac = (abs % FACTOR).toString().padStart(SCALE, "0").replace(/0+$/, "");
  if (frac.length < minDecimals) frac = frac.padEnd(minDecimals, "0");
  const out = frac ? `${int}.${frac}` : `${int}`;
  return neg && abs !== 0n ? `-${out}` : out;
}

export const normalize = (v: Decimal | null | undefined): Decimal => fromScaled(toScaled(v));
export const add = (...vals: (Decimal | null | undefined)[]): Decimal =>
  fromScaled(vals.reduce<bigint>((acc, v) => acc + toScaled(v), 0n));
export const sub = (a: Decimal, b: Decimal): Decimal => fromScaled(toScaled(a) - toScaled(b));
export const mul = (a: Decimal, b: Decimal): Decimal => fromScaled(roundHalfUp(toScaled(a) * toScaled(b), FACTOR));
export const neg = (a: Decimal): Decimal => fromScaled(-toScaled(a));
export const abs = (a: Decimal): Decimal => {
  const n = toScaled(a);
  return fromScaled(n < 0n ? -n : n);
};
export const cmp = (a: Decimal, b: Decimal): -1 | 0 | 1 => {
  const d = toScaled(a) - toScaled(b);
  return d === 0n ? 0 : d < 0n ? -1 : 1;
};
export const isZero = (a: Decimal | null | undefined): boolean => toScaled(a) === 0n;
export const isNegative = (a: Decimal): boolean => toScaled(a) < 0n;
export const sum = (vals: (Decimal | null | undefined)[]): Decimal => add(...vals);

/** Round to `dp` decimals (half-up) and return a fixed-decimals string. */
export function round(value: Decimal, dp = 2): Decimal {
  const n = toScaled(value);
  const div = 10n ** BigInt(SCALE - dp);
  const r = roundHalfUp(n, div) * div;
  return fromScaled(r, dp);
}

/** Indian digit grouping: 1234567 → 12,34,567 */
export function groupIndian(intDigits: string): string {
  if (intDigits.length <= 3) return intDigits;
  const last3 = intDigits.slice(-3);
  const rest = intDigits.slice(0, -3).replace(/\B(?=(\d{2})+(?!\d))/g, ",");
  return `${rest},${last3}`;
}

export interface FormatOptions {
  decimals?: number;
  symbol?: string | false;
  /** Render negatives as "(1,234.00)" instead of "-1,234.00". */
  parens?: boolean;
}

/** Format a decimal string as `₹12,34,567.00`. */
export function formatMoney(value: Decimal | null | undefined, opts: FormatOptions = {}): string {
  const { decimals = 2, symbol = "₹", parens = false } = opts;
  const fixed = round(value ?? "0", decimals);
  const negative = fixed.startsWith("-");
  const [i = "0", f] = (negative ? fixed.slice(1) : fixed).split(".");
  const body = `${groupIndian(i)}${f !== undefined && decimals > 0 ? `.${f}` : ""}`;
  const withSym = symbol ? `${symbol}${body}` : body;
  if (!negative) return withSym;
  return parens ? `(${withSym})` : `-${withSym}`;
}

/** Format a quantity (no symbol, up to 4 dp, trailing zeros trimmed). */
export function formatQty(value: Decimal | null | undefined, maxDecimals = 4): string {
  const r = round(value ?? "0", maxDecimals);
  const [i = "0", f = ""] = r.replace("-", "").split(".");
  const frac = f.replace(/0+$/, "");
  return `${r.startsWith("-") ? "-" : ""}${groupIndian(i)}${frac ? `.${frac}` : ""}`;
}

/**
 * Parse user input ("₹ 12,34,567.5", "1,000", "-25", "(25)") into a canonical decimal string.
 * Returns null when the input is not a valid number or has more than `maxDecimals` decimals.
 */
export function parseMoneyInput(input: string, maxDecimals = SCALE): Decimal | null {
  let s = input.trim().replace(/[₹\s,]/g, "").replace(/^(rs\.?|inr)/i, "");
  if (s === "") return null;
  let negative = false;
  if (/^\(.*\)$/.test(s)) {
    negative = true;
    s = s.slice(1, -1);
  }
  if (s.startsWith("-")) {
    negative = !negative;
    s = s.slice(1);
  }
  if (s.startsWith(".")) s = `0${s}`;
  if (s.endsWith(".")) s = s.slice(0, -1);
  if (!/^\d+(\.\d+)?$/.test(s)) return null;
  const frac = s.split(".")[1] ?? "";
  if (frac.length > maxDecimals) return null;
  const canonical = fromScaled(toScaled(s));
  return negative && canonical !== "0" ? `-${canonical}` : canonical;
}

export const isDecimal = (s: string): boolean => /^-?\d+(\.\d{1,4})?$/.test(s);
