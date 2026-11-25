// Money/decimal helpers. Values travel as strings (^-?\d+(\.\d{1,4})?$) and are held as BigInt scaled by 10^4.
// Never use floats for money.

export const SCALE = 4;
const FACTOR = 10n ** BigInt(SCALE);
const DECIMAL_RE = /^-?\d+(\.\d{1,4})?$/;

export function isDecimalString(v: unknown): v is string {
  return typeof v === "string" && DECIMAL_RE.test(v.trim());
}

/** "1234.5" → 12345000n (scaled by 10^4). Throws on invalid input. */
export function parseDecimal(v: string): bigint {
  const s = v.trim();
  if (!DECIMAL_RE.test(s)) throw new Error(`Invalid decimal: ${v}`);
  const neg = s.startsWith("-");
  const [int = "0", frac = ""] = (neg ? s.slice(1) : s).split(".");
  const scaled = BigInt(int) * FACTOR + BigInt((frac + "0000").slice(0, SCALE));
  return neg ? -scaled : scaled;
}

/** 12345000n → "1234.5000" (always 4 dp, contract-compatible). */
export function toDecimalString(v: bigint, dp: number = SCALE): string {
  const neg = v < 0n;
  let abs = neg ? -v : v;
  if (dp < SCALE) {
    const div = 10n ** BigInt(SCALE - dp);
    abs = (abs + div / 2n) / div; // round half up
    const f = 10n ** BigInt(dp);
    const int = abs / f;
    const frac = dp > 0 ? "." + (abs % f).toString().padStart(dp, "0") : "";
    return `${neg && abs !== 0n ? "-" : ""}${int}${frac}`;
  }
  const int = abs / FACTOR;
  const frac = (abs % FACTOR).toString().padStart(SCALE, "0");
  return `${neg ? "-" : ""}${int}.${frac}`;
}

/** Normalizes user input ("1,20,000.5") to a contract decimal string or null if invalid. */
export function normalizeDecimalInput(input: string): string | null {
  const s = input.replace(/[,\s₹]/g, "");
  if (s === "" || !DECIMAL_RE.test(s)) return null;
  return toDecimalString(parseDecimal(s)).replace(/\.?0+$/, "") || "0";
}

/** Indian digit grouping: 12345678 → "1,23,45,678". */
export function groupIndian(intDigits: string): string {
  if (intDigits.length <= 3) return intDigits;
  const last3 = intDigits.slice(-3);
  const rest = intDigits.slice(0, -3).replace(/\B(?=(\d{2})+(?!\d))/g, ",");
  return `${rest},${last3}`;
}

/** "250000.5" → "₹ 2,50,000.50" */
export function formatINR(v: string | null | undefined, opts: { dp?: number; symbol?: boolean } = {}): string {
  if (v == null || !isDecimalString(v)) return "—";
  const dp = opts.dp ?? 2;
  const s = toDecimalString(parseDecimal(v), dp);
  const neg = s.startsWith("-");
  const [int = "0", frac] = (neg ? s.slice(1) : s).split(".");
  const body = groupIndian(int) + (frac ? `.${frac}` : "");
  return `${neg ? "-" : ""}${opts.symbol === false ? "" : "₹ "}${body}`;
}

/** Compact Indian units: "18600000" → "₹ 1.86 Cr", "450000" → "₹ 4.50 L". */
export function formatINRCompact(v: string | null | undefined): string {
  if (v == null || !isDecimalString(v)) return "—";
  const x = parseDecimal(v);
  const abs = x < 0n ? -x : x;
  const crore = 10_000_000n * FACTOR;
  const lakh = 100_000n * FACTOR;
  const fmt = (unit: bigint, suffix: string) => `${formatINR(toDecimalString((x * FACTOR) / unit), { dp: 2 })} ${suffix}`;
  if (abs >= crore) return fmt(crore, "Cr");
  if (abs >= lakh) return fmt(lakh, "L");
  return formatINR(v, { dp: 0 });
}

export function sumDecimals(values: string[]): string {
  return toDecimalString(values.reduce((acc, v) => acc + parseDecimal(v), 0n));
}

/** Formats a percentage-like decimal string without trailing zeros: "18.0000" → "18%". */
export function formatRate(v: string | null | undefined): string {
  if (v == null || !isDecimalString(v)) return "—";
  return `${toDecimalString(parseDecimal(v)).replace(/\.?0+$/, "")}%`;
}

export function formatBytes(n: number | null | undefined): string {
  if (n == null) return "—";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let i = 0;
  let v = n;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i++;
  }
  return `${v.toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}
