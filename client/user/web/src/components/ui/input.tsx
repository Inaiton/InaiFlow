import { forwardRef, type InputHTMLAttributes, type ReactNode, type TextareaHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export const inputClass =
  "h-10 w-full min-w-0 rounded-lg border border-line bg-surface px-2.5 text-[13px] text-fg placeholder:text-fg-faint outline-none transition-colors focus:border-primary focus:ring-2 focus:ring-primary/15 disabled:bg-subtle disabled:text-fg-muted aria-[invalid=true]:border-danger";

export interface InputProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "prefix"> {
  prefix?: ReactNode;
  suffix?: ReactNode;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input({ className, prefix, suffix, ...props }, ref) {
  if (!prefix && !suffix) return <input ref={ref} className={cn(inputClass, className)} {...props} />;
  return (
    <span
      className={cn(
        "flex h-10 w-full items-center rounded-lg border border-line bg-surface focus-within:border-primary focus-within:ring-2 focus-within:ring-primary/15 has-[[aria-invalid=true]]:border-danger",
        className,
      )}
    >
      {prefix ? <span className="pl-2.5 text-[12px] text-fg-muted">{prefix}</span> : null}
      <input ref={ref} className="h-full min-w-0 flex-1 bg-transparent px-2.5 text-[13px] text-fg outline-none placeholder:text-fg-faint" {...props} />
      {suffix ? <span className="pr-2.5 text-[12px] whitespace-nowrap text-fg-muted">{suffix}</span> : null}
    </span>
  );
});

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(function Textarea(
  { className, rows = 3, ...props },
  ref,
) {
  return <textarea ref={ref} rows={rows} className={cn(inputClass, "h-auto resize-y py-2", className)} {...props} />;
});
