import { comboLabel } from "@/core/shortcuts/parser";
import { cn } from "@/lib/utils";

export function Kbd({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <kbd className={cn("inline-flex items-center rounded-md border border-line bg-subtle px-1.5 py-0.5 font-sans text-[10.5px] font-medium whitespace-nowrap text-fg-muted", className)}>
      {children}
    </kbd>
  );
}

/** Render a combo like "alt+g" as "Alt G". */
export function KbdCombo({ combo, className }: { combo: string; className?: string }) {
  return <Kbd className={className}>{comboLabel(combo).join(" ")}</Kbd>;
}
