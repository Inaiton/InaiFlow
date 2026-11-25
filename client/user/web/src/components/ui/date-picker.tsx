import { forwardRef } from "react";
import { cn } from "@/lib/utils";
import { inputClass } from "./input";

interface DatePickerProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, "type" | "value" | "onChange"> {
  /** ISO `YYYY-MM-DD` or "" */
  value: string | null | undefined;
  onValueChange: (value: string | null) => void;
  /** "date" (default) or "month" (`YYYY-MM`). */
  mode?: "date" | "month";
}

/** Native date input styled to tokens — accessible, keyboard friendly, no extra JS. */
export const DatePicker = forwardRef<HTMLInputElement, DatePickerProps>(function DatePicker({ value, onValueChange, mode = "date", className, ...props }, ref) {
  return (
    <input
      ref={ref}
      type={mode}
      value={value ?? ""}
      onChange={(e) => onValueChange(e.target.value || null)}
      className={cn(inputClass, "tabular", className)}
      {...props}
    />
  );
});
