import { AlertTriangle, CheckCircle2, Info, Loader2, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { TONE_CLASSES, type Tone } from "./badge";
import { IconTile } from "./icon-tile";

export function Spinner({ className, label = "Loading" }: { className?: string; label?: string }) {
  return <Loader2 className={cn("size-5 animate-spin text-fg-muted", className)} aria-label={label} role="status" />;
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded-md bg-subtle", className)} aria-hidden />;
}

interface EmptyStateProps {
  icon?: LucideIcon;
  tone?: Tone;
  title: ReactNode;
  description?: ReactNode;
  action?: ReactNode;
  className?: string;
}

/** Calm empty state with one clear next action. */
export function EmptyState({ icon = Info, tone = "gray", title, description, action, className }: EmptyStateProps) {
  return (
    <div className={cn("flex flex-col items-center justify-center gap-3 rounded-2xl border border-dashed border-line-strong px-6 py-10 text-center", className)}>
      <IconTile icon={icon} tone={tone} size={40} />
      <div className="flex max-w-md flex-col gap-1">
        <p className="text-sm font-semibold text-fg">{title}</p>
        {description ? <p className="text-[12.5px] text-fg-muted">{description}</p> : null}
      </div>
      {action}
    </div>
  );
}

const HINT_ICON: Partial<Record<Tone, LucideIcon>> = { success: CheckCircle2, warning: AlertTriangle, danger: AlertTriangle };

/** Hint / callout (design `hint()`): tinted panel with an icon and optional title. */
export function Hint({ tone = "sky", title, children, action, className }: { tone?: Tone; title?: ReactNode; children: ReactNode; action?: ReactNode; className?: string }) {
  const t = TONE_CLASSES[tone];
  const Icon = HINT_ICON[tone] ?? Info;
  return (
    <div role={tone === "danger" ? "alert" : "note"} className={cn("flex items-start gap-2.5 rounded-xl px-3.5 py-3 text-[12.5px]", t.tint, className)}>
      <Icon className={cn("mt-0.5 size-4 flex-none", t.text)} aria-hidden />
      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        {title ? <span className={cn("font-semibold", t.text)}>{title}</span> : null}
        <span className="text-fg-3">{children}</span>
      </div>
      {action}
    </div>
  );
}

/** Inline error block with retry for failed queries. */
export function ErrorState({ message, onRetry, className }: { message: string; onRetry?: () => void; className?: string }) {
  return (
    <Hint tone="danger" title="Couldn’t load this" className={className} action={onRetry ? <button type="button" onClick={onRetry} className="text-[12.5px] font-semibold text-danger-text underline">Retry</button> : undefined}>
      {message}
    </Hint>
  );
}

export function Meter({ value, max, tone = "teal", label, detail }: { value: number; max: number; tone?: Tone; label?: ReactNode; detail?: ReactNode }) {
  const pct = max > 0 ? Math.min(100, Math.round((value / max) * 100)) : 0;
  const barTone: Tone = pct >= 90 ? "danger" : pct >= 75 ? "warning" : tone;
  return (
    <div className="flex flex-col gap-1.5">
      {label || detail ? (
        <div className="flex items-baseline justify-between gap-2 text-[13px]">
          <span className="font-medium text-fg">{label}</span>
          <span className="tabular text-fg-muted">{detail}</span>
        </div>
      ) : null}
      <div className="h-2 rounded-[3px] bg-line" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100} aria-label={typeof label === "string" ? label : undefined}>
        <div className={cn("h-2 rounded-[3px]", TONE_CLASSES[barTone].solid)} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
