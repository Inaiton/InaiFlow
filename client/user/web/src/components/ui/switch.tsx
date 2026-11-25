"use client";

import { Check } from "lucide-react";
import { Checkbox as CheckboxPrimitive, Switch as SwitchPrimitive } from "radix-ui";
import { useId, type ReactNode } from "react";
import { cn } from "@/lib/utils";

export function Switch({ className, ...props }: React.ComponentProps<typeof SwitchPrimitive.Root>) {
  return (
    <SwitchPrimitive.Root
      className={cn("inline-flex h-6 w-10 flex-none items-center rounded-[7px] bg-line-strong p-0.5 transition-colors data-[state=checked]:bg-teal disabled:opacity-50", className)}
      {...props}
    >
      <SwitchPrimitive.Thumb className="size-5 rounded-[5px] bg-white shadow-xs transition-transform data-[state=checked]:translate-x-4" />
    </SwitchPrimitive.Root>
  );
}

/** Labelled switch row (design `switch()`). */
export function SwitchRow({ label, description, checked, onCheckedChange, disabled }: { label: ReactNode; description?: ReactNode; checked: boolean; onCheckedChange: (v: boolean) => void; disabled?: boolean }) {
  const id = useId();
  return (
    <div className="flex items-center gap-3 border-b border-subtle py-2.5 last:border-0">
      <label htmlFor={id} className="flex flex-1 cursor-pointer flex-col gap-0.5">
        <span className="text-[13px] font-semibold text-fg">{label}</span>
        {description ? <span className="text-xs text-fg-muted">{description}</span> : null}
      </label>
      <Switch id={id} checked={checked} onCheckedChange={onCheckedChange} disabled={disabled} />
    </div>
  );
}

export function Checkbox({ className, ...props }: React.ComponentProps<typeof CheckboxPrimitive.Root>) {
  return (
    <CheckboxPrimitive.Root
      className={cn("grid size-[18px] flex-none place-items-center rounded-[5px] border border-line-strong bg-surface data-[state=checked]:border-primary data-[state=checked]:bg-primary disabled:opacity-50", className)}
      {...props}
    >
      <CheckboxPrimitive.Indicator>
        <Check className="size-3 text-white" strokeWidth={3} />
      </CheckboxPrimitive.Indicator>
    </CheckboxPrimitive.Root>
  );
}

export function CheckboxRow({ label, description, checked, onCheckedChange, disabled }: { label: ReactNode; description?: ReactNode; checked: boolean; onCheckedChange: (v: boolean) => void; disabled?: boolean }) {
  const id = useId();
  return (
    <div className="flex items-start gap-2.5">
      <Checkbox id={id} checked={checked} onCheckedChange={(v) => onCheckedChange(v === true)} disabled={disabled} className="mt-0.5" />
      <label htmlFor={id} className="flex cursor-pointer flex-col gap-0.5 text-[13px]">
        <span className="font-medium text-fg">{label}</span>
        {description ? <span className="text-xs text-fg-muted">{description}</span> : null}
      </label>
    </div>
  );
}
