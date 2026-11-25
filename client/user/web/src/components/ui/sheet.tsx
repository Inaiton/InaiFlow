"use client";

import { X } from "lucide-react";
import { Dialog as DialogPrimitive } from "radix-ui";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export const Sheet = DialogPrimitive.Root;
export const SheetTrigger = DialogPrimitive.Trigger;
export const SheetClose = DialogPrimitive.Close;

interface SheetContentProps extends Omit<React.ComponentProps<typeof DialogPrimitive.Content>, "title"> {
  title: ReactNode;
  description?: ReactNode;
  footer?: ReactNode;
  side?: "right" | "left";
  width?: number;
}

/** Side drawer (design `drawer()`), used for detail panels like audit events. */
export function SheetContent({ title, description, footer, side = "right", width = 480, className, children, style, ...props }: SheetContentProps) {
  return (
    <DialogPrimitive.Portal>
      <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-fg/30 animate-fade-in" />
      <DialogPrimitive.Content
        style={{ width: `min(${width}px, 100vw)`, ...style }}
        className={cn(
          "fixed inset-y-0 z-50 flex flex-col border-line bg-surface shadow-pop outline-none animate-slide-in-right",
          side === "right" ? "right-0 border-l" : "left-0 border-r",
          className,
        )}
        {...props}
      >
        <div className="flex items-start gap-3 border-b border-line px-5 py-4">
          <div className="flex min-w-0 flex-1 flex-col gap-1">
            <DialogPrimitive.Title className="text-base font-semibold text-fg">{title}</DialogPrimitive.Title>
            <DialogPrimitive.Description className={description ? "text-[12.5px] text-fg-muted" : "sr-only"}>
              {description ?? (typeof title === "string" ? title : "Panel")}
            </DialogPrimitive.Description>
          </div>
          <DialogPrimitive.Close className="grid size-8 place-items-center rounded-lg text-fg-muted hover:bg-subtle" aria-label="Close">
            <X className="size-4" />
          </DialogPrimitive.Close>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">{children}</div>
        {footer ? <div className="flex flex-wrap justify-end gap-2 border-t border-line px-5 py-3.5">{footer}</div> : null}
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  );
}
