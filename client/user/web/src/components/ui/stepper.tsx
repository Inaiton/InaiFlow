import { Check } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export interface StepItem {
  title: string;
  description?: string;
}

/** Horizontal wizard stepper (Org create: Essentials → Statutory → FY → Review). */
export function Stepper({ steps, current, className }: { steps: StepItem[]; current: number; className?: string }) {
  return (
    <ol className={cn("grid gap-2 sm:grid-cols-[repeat(auto-fit,minmax(150px,1fr))]", className)} aria-label="Progress">
      {steps.map((s, i) => {
        const done = i < current;
        const active = i === current;
        return (
          <li key={s.title} aria-current={active ? "step" : undefined} className={cn("flex items-center gap-2.5 rounded-xl border px-3 py-2.5", active ? "border-primary bg-primary-tint" : "border-line bg-surface")}>
            <span className={cn("grid size-7 flex-none place-items-center rounded-lg text-xs font-semibold", done ? "bg-success text-white" : active ? "bg-primary text-white" : "bg-subtle text-fg-muted")}>
              {done ? <Check className="size-4" aria-hidden /> : i + 1}
            </span>
            <span className="flex min-w-0 flex-col">
              <span className={cn("truncate text-[13px] font-semibold", active ? "text-primary-text" : "text-fg")}>{s.title}</span>
              {s.description ? <span className="truncate text-[11.5px] text-fg-muted">{s.description}</span> : null}
            </span>
          </li>
        );
      })}
    </ol>
  );
}

export interface GuideStep {
  title: string;
  description?: string;
  href?: string;
  done?: boolean;
  action?: ReactNode;
}

/** "Get started" checklist (design `guide()`). */
export function GetStartedGuide({ title = "Get started", steps, className }: { title?: string; steps: GuideStep[]; className?: string }) {
  const done = steps.filter((s) => s.done).length;
  return (
    <section className={cn("flex flex-col gap-3 rounded-2xl border border-line bg-surface px-5 py-4", className)} aria-label={title}>
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-[15px] font-semibold text-fg">{title}</h2>
        <span className="text-xs text-fg-muted">{done} of {steps.length} done</span>
      </div>
      <ol className="flex flex-col gap-2">
        {steps.map((s, i) => {
          const body = (
            <>
              <span className={cn("grid size-6 flex-none place-items-center rounded-md text-[11px] font-semibold", s.done ? "bg-success text-white" : "bg-subtle text-fg-muted")}>
                {s.done ? <Check className="size-3.5" aria-hidden /> : i + 1}
              </span>
              <span className="flex min-w-0 flex-1 flex-col">
                <span className={cn("text-[13px] font-semibold", s.done ? "text-fg-muted line-through" : "text-fg")}>{s.title}</span>
                {s.description ? <span className="text-xs text-fg-muted">{s.description}</span> : null}
              </span>
              {s.action}
            </>
          );
          return (
            <li key={s.title}>
              {s.href && !s.done ? (
                <Link href={s.href} className="flex items-center gap-3 rounded-xl border border-line bg-canvas px-3 py-2.5 no-underline hover:border-line-strong">
                  {body}
                </Link>
              ) : (
                <div className="flex items-center gap-3 rounded-xl border border-line bg-canvas px-3 py-2.5">{body}</div>
              )}
            </li>
          );
        })}
      </ol>
    </section>
  );
}
