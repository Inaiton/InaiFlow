import { Label as LabelPrimitive } from "radix-ui";
import { cloneElement, isValidElement, useId, type ReactElement, type ReactNode } from "react";
import { cn } from "@/lib/utils";

export function Label({ className, ...props }: React.ComponentProps<typeof LabelPrimitive.Root>) {
  return <LabelPrimitive.Root className={cn("text-[12.5px] font-medium text-fg-2", className)} {...props} />;
}

interface FieldProps {
  label: ReactNode;
  hint?: ReactNode;
  error?: string;
  required?: boolean;
  className?: string;
  /** A single form control; receives id / aria-invalid / aria-describedby. */
  children: ReactElement<Record<string, unknown>>;
}

/** Label + control + hint/error, wired for accessibility. */
export function Field({ label, hint, error, required, className, children }: FieldProps) {
  const id = useId();
  const controlId = (children.props.id as string | undefined) ?? id;
  const describedBy = error ? `${id}-err` : hint ? `${id}-hint` : undefined;
  const control = isValidElement(children)
    ? cloneElement(children, {
        id: controlId,
        "aria-invalid": error ? true : undefined,
        "aria-describedby": describedBy,
        "aria-required": required || undefined,
      })
    : children;
  return (
    <div className={cn("flex min-w-0 flex-col gap-1.5", className)}>
      <Label htmlFor={controlId}>
        {label}
        {required ? <span className="ml-0.5 text-danger-text" aria-hidden>*</span> : null}
      </Label>
      {control}
      {error ? (
        <span id={`${id}-err`} role="alert" className="text-[11.5px] text-danger-text">
          {error}
        </span>
      ) : hint ? (
        <span id={`${id}-hint`} className="text-[11.5px] text-fg-muted">
          {hint}
        </span>
      ) : null}
    </div>
  );
}

/** Responsive wrap of fields (matches the design's `fields()` rows). */
export function FieldRow({ className, children }: { className?: string; children: ReactNode }) {
  return <div className={cn("grid grid-cols-1 gap-3.5 sm:grid-cols-2", className)}>{children}</div>;
}
