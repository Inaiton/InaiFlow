import { cn } from "@/lib/utils";

/** Calm progress bar (Meter turns red near 100%, which suits quotas, not progress). */
export function Progress({ value, label, tone = "bg-success", className }: { value: number; label?: string; tone?: string; className?: string }) {
  const pct = Math.max(0, Math.min(100, Math.round(value)));
  return (
    <div className={cn("flex items-center gap-2", className)}>
      <div className="h-1.5 flex-1 rounded-[3px] bg-line" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100} aria-label={label ?? "Progress"}>
        <div className={cn("h-1.5 rounded-[3px]", tone)} style={{ width: `${pct}%` }} />
      </div>
      <span className="tabular w-9 text-right text-xs text-fg-muted">{pct}%</span>
    </div>
  );
}
