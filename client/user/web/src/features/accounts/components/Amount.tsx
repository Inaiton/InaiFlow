import type { Decimal } from "@/core/money";
import { isNegative } from "@/core/money";
import { cn } from "@/lib/utils";
import { amt, amtOrBlank, drcr, type DrCr } from "../lib/format";

/** Right-aligned tabular amount; `blankZero` for Tally-style empty cells. */
export function Amt({ v, blankZero, className, strong }: { v: Decimal | null | undefined; blankZero?: boolean; className?: string; strong?: boolean }) {
  return (
    <span className={cn("tabular whitespace-nowrap", strong && "font-semibold text-ink", v && isNegative(v) && "text-danger-text", className)}>
      {blankZero ? amtOrBlank(v) : amt(v)}
    </span>
  );
}

export function Bal({ v, type, className }: { v: Decimal | null | undefined; type: DrCr | null | undefined; className?: string }) {
  return <span className={cn("tabular whitespace-nowrap", className)}>{drcr(v, type)}</span>;
}
