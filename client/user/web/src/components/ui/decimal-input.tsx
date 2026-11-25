"use client";

import { forwardRef, useState, type FocusEvent, type KeyboardEvent } from "react";
import { formatMoney, formatQty, parseMoneyInput, type Decimal } from "@/core/money";
import { cn } from "@/lib/utils";
import { Input } from "./input";

interface DecimalInputProps {
  value: Decimal | null | undefined;
  /** Receives a canonical decimal string ("1234.5") or null when empty/invalid. */
  onValueChange: (value: Decimal | null) => void;
  /** Max decimals the user may type (contract allows 4). */
  decimals?: number;
  /** "money" shows ₹ grouping on blur; "qty" shows plain grouping. */
  kind?: "money" | "qty";
  allowNegative?: boolean;
  prefix?: string;
  suffix?: string;
  placeholder?: string;
  disabled?: boolean;
  className?: string;
  id?: string;
  name?: string;
  onBlur?: () => void;
  onKeyDown?: (e: KeyboardEvent<HTMLInputElement>) => void;
  "aria-invalid"?: boolean;
  "aria-describedby"?: string;
  "aria-label"?: string;
}

/**
 * Text input for money/quantities. Never uses floats: the value is a decimal string.
 * Shows Indian grouping when not focused; raw digits while editing.
 */
export const DecimalInput = forwardRef<HTMLInputElement, DecimalInputProps>(function DecimalInput(
  { value, onValueChange, decimals = 2, kind = "money", allowNegative = false, prefix, suffix, placeholder = "0.00", className, onBlur, ...rest },
  ref,
) {
  const [focused, setFocused] = useState(false);
  // The draft is only meaningful while focused; on focus it is re-seeded from `value`.
  const [draft, setDraft] = useState("");

  const display = focused
    ? draft
    : value
      ? kind === "money"
        ? formatMoney(value, { symbol: false, decimals })
        : formatQty(value, decimals)
      : "";

  return (
    <Input
      ref={ref}
      inputMode="decimal"
      autoComplete="off"
      prefix={prefix}
      suffix={suffix}
      placeholder={placeholder}
      className={cn("tabular text-right", className)}
      value={display}
      onFocus={(e: FocusEvent<HTMLInputElement>) => {
        setFocused(true);
        setDraft(value ?? "");
        requestAnimationFrame(() => e.target.select());
      }}
      onChange={(e) => {
        const raw = e.target.value;
        if (!/^[-\d.,₹\s()]*$/.test(raw)) return;
        setDraft(raw);
        const parsed = parseMoneyInput(raw, decimals);
        if (raw.trim() === "") onValueChange(null);
        else if (parsed !== null && (allowNegative || !parsed.startsWith("-"))) onValueChange(parsed);
      }}
      onBlur={() => {
        setFocused(false);
        onBlur?.();
      }}
      {...rest}
    />
  );
});
