"use client";

import { ChevronDown } from "lucide-react";
import { Collapsible } from "radix-ui";
import { useState, type ReactNode } from "react";
import { cn } from "@/lib/utils";

/** Titled form/page section (design `section()`). */
export function Section({ title, description, actions, children, className }: { title: ReactNode; description?: ReactNode; actions?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={cn("flex flex-col gap-3.5", className)}>
      <div className="flex flex-wrap items-end gap-2">
        <div className="flex min-w-0 flex-1 flex-col gap-0.5">
          <h3 className="text-[14px] font-semibold text-fg">{title}</h3>
          {description ? <p className="text-[12.5px] text-fg-muted">{description}</p> : null}
        </div>
        {actions}
      </div>
      {children}
    </section>
  );
}

/** Collapsed-by-default "Advanced" area — keeps screens calm (plan §3.9). */
export function AdvancedSection({ title = "Advanced", description, defaultOpen = false, children }: { title?: string; description?: string; defaultOpen?: boolean; children: ReactNode }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <Collapsible.Root open={open} onOpenChange={setOpen} className="rounded-xl border border-line">
      <Collapsible.Trigger className="flex w-full items-center gap-2 px-3.5 py-2.5 text-left">
        <span className="flex flex-1 flex-col">
          <span className="text-[13px] font-semibold text-fg">{title}</span>
          {description ? <span className="text-xs text-fg-muted">{description}</span> : null}
        </span>
        <ChevronDown className={cn("size-4 text-fg-muted transition-transform", open && "rotate-180")} aria-hidden />
      </Collapsible.Trigger>
      <Collapsible.Content className="border-t border-line px-3.5 py-3.5">{children}</Collapsible.Content>
    </Collapsible.Root>
  );
}
