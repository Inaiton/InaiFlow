import { forwardRef, type InputHTMLAttributes } from "react";
import { cn } from "@/lib/utils";
import { inputClass } from "@/components/ui/input";

/** One-time code input (6 digits by default). Accessible single field with numeric keypad. */
export const CodeInput = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement> & { digitsOnly?: boolean }>(function CodeInput(
  { className, digitsOnly = true, ...props },
  ref,
) {
  return (
    <input
      ref={ref}
      inputMode={digitsOnly ? "numeric" : "text"}
      autoComplete="one-time-code"
      maxLength={digitsOnly ? 6 : 32}
      placeholder={digitsOnly ? "••••••" : "Code"}
      className={cn(inputClass, "tabular h-12 text-center text-lg tracking-[0.5em]", className)}
      {...props}
    />
  );
});
