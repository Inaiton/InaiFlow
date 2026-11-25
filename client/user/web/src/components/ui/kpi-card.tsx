import { ArrowRight, type LucideIcon } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { Badge, type Tone } from "./badge";
import { IconTile } from "./icon-tile";

interface KpiCardProps {
  title: string;
  value: ReactNode;
  icon: LucideIcon;
  tone?: Tone;
  change?: { label: string; tone?: Tone };
  caption?: ReactNode;
  href?: string;
  className?: string;
}

/** Compact KPI card (design `kpi()`): soft grey surface, tinted rounded-square icon tile. */
export function KpiCard({ title, value, icon, tone = "indigo", change, caption, href, className }: KpiCardProps) {
  return (
    <article className={cn("flex min-w-0 flex-col gap-1.5 rounded-2xl bg-muted-surface py-3.5 pr-3.5 pl-4", className)}>
      <div className="flex items-center justify-between gap-2.5">
        <span className="text-[13.5px] font-medium text-fg">{title}</span>
        <IconTile icon={icon} tone={tone} size={34} />
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <span className="tabular text-2xl font-semibold tracking-[-0.3px] whitespace-nowrap text-ink">{value}</span>
        {change ? <Badge tone={change.tone ?? "success"}>{change.label}</Badge> : null}
      </div>
      <div className="flex min-h-[30px] items-center justify-between gap-2.5">
        <span className="text-xs text-fg-muted">{caption}</span>
        {href ? (
          <Link href={href} aria-label={`Open ${title}`} className="grid size-[30px] flex-none place-items-center rounded-lg bg-surface text-fg shadow-xs hover:bg-subtle">
            <ArrowRight className="size-[15px]" strokeWidth={2} />
          </Link>
        ) : null}
      </div>
    </article>
  );
}

export function KpiGrid({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <section aria-label="Key figures" className={cn("grid grid-cols-[repeat(auto-fit,minmax(210px,1fr))] gap-4", className)}>
      {children}
    </section>
  );
}
