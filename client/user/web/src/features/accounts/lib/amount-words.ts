import { round } from "@/core/money";

const ONES = [
  "", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten", "Eleven", "Twelve", "Thirteen",
  "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen",
];
const TENS = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"];

function twoDigits(n: number): string {
  if (n < 20) return ONES[n] ?? "";
  const t = TENS[Math.floor(n / 10)] ?? "";
  const o = ONES[n % 10] ?? "";
  return o ? `${t} ${o}` : t;
}

function threeDigits(n: number): string {
  const h = Math.floor(n / 100);
  const rest = n % 100;
  const parts: string[] = [];
  if (h) parts.push(`${ONES[h]} Hundred`);
  if (rest) parts.push(twoDigits(rest));
  return parts.join(" ");
}

/** Whole number → words in the Indian system (Crore, Lakh, Thousand, Hundred). Uses BigInt, no floats. */
export function integerToIndianWords(n: bigint): string {
  if (n < 0n) return `Minus ${integerToIndianWords(-n)}`;
  if (n === 0n) return "Zero";
  const CRORE = 10_000_000n;
  const parts: string[] = [];
  const crore = n / CRORE;
  let rest = n % CRORE;
  if (crore > 0n) parts.push(`${integerToIndianWords(crore)} Crore`);
  const lakh = Number(rest / 100_000n);
  rest %= 100_000n;
  const thousand = Number(rest / 1000n);
  const below = Number(rest % 1000n);
  if (lakh) parts.push(`${twoDigits(lakh)} Lakh`);
  if (thousand) parts.push(`${twoDigits(thousand)} Thousand`);
  if (below) parts.push(threeDigits(below));
  return parts.join(" ");
}

export interface AmountWordsOptions {
  /** Currency prefix (design: "INR"). */
  prefix?: string;
  /** Name of the minor unit. */
  minor?: string;
}

/**
 * Amount in words for invoices: `amountInWords("291318")` → "INR Two Lakh Ninety One Thousand Three Hundred Eighteen Only";
 * paise are spelt out: `amountInWords("1250.40")` → "INR One Thousand Two Hundred Fifty and Forty Paise Only".
 */
export function amountInWords(value: string | null | undefined, opts: AmountWordsOptions = {}): string {
  const { prefix = "INR", minor = "Paise" } = opts;
  const fixed = round(value ?? "0", 2);
  const negative = fixed.startsWith("-");
  const [i = "0", f = "00"] = (negative ? fixed.slice(1) : fixed).split(".");
  const rupees = BigInt(i);
  const paise = Number(f.padEnd(2, "0"));
  let words = rupees === 0n && paise > 0 ? "" : integerToIndianWords(rupees);
  if (paise > 0) words = words ? `${words} and ${twoDigits(paise)} ${minor}` : `${twoDigits(paise)} ${minor}`;
  const body = `${negative ? "Minus " : ""}${words} Only`;
  return prefix ? `${prefix} ${body}` : body;
}
