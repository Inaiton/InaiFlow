"use client";

import { Check, Copy } from "lucide-react";
import { useState, type ReactNode } from "react";
import { Button } from "./button";
import { cn } from "@/lib/utils";
import type { Tone } from "./badge";

export function PageHeader({ title, description, actions, crumbs }: { title: ReactNode; description?: ReactNode; actions?: ReactNode; crumbs?: ReactNode }) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div className="min-w-0">
        {crumbs ? <div className="mb-1 text-xs text-faint">{crumbs}</div> : null}
        <h1 className="text-xl font-semibold text-ink">{title}</h1>
        {description ? <p className="mt-0.5 text-[13px] text-muted">{description}</p> : null}
      </div>
      {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
    </div>
  );
}

const tileTones: Record<Tone, string> = {
  success: "bg-success-tint text-success-ink",
  warning: "bg-warning-tint text-warning-ink",
  danger: "bg-danger-tint text-danger-ink",
  indigo: "bg-indigo-tint text-indigo",
  sky: "bg-sky-tint text-sky",
  violet: "bg-violet-tint text-violet",
  teal: "bg-teal-tint text-teal",
  accent: "bg-primary-tint text-primary",
  orange: "bg-orange-tint text-orange",
  gray: "bg-subtle text-muted",
};

export function KpiCard({ label, value, sub, icon, tone = "gray" }: { label: string; value: ReactNode; sub?: ReactNode; icon?: ReactNode; tone?: Tone }) {
  return (
    <div className="rounded-lg border border-line bg-white p-3.5">
      <div className="flex items-center gap-2">
        {icon ? <span className={cn("flex size-7 items-center justify-center rounded-md [&_svg]:size-4", tileTones[tone])}>{icon}</span> : null}
        <span className="text-[13px] text-muted">{label}</span>
      </div>
      <div className="mt-2 text-2xl font-semibold tabular-nums text-ink">{value}</div>
      {sub ? <div className="mt-0.5 text-xs text-faint">{sub}</div> : null}
    </div>
  );
}

export function CopyButton({ value, label = "Copy" }: { value: string; label?: string }) {
  const [done, setDone] = useState(false);
  return (
    <Button
      size="sm"
      onClick={async () => {
        await navigator.clipboard.writeText(value);
        setDone(true);
        setTimeout(() => setDone(false), 1500);
      }}
    >
      {done ? <Check /> : <Copy />}
      {done ? "Copied" : label}
    </Button>
  );
}

export function DefinitionList({ items }: { items: [string, ReactNode][] }) {
  return (
    <dl className="grid grid-cols-1 gap-x-6 gap-y-3 sm:grid-cols-2">
      {items.map(([k, v]) => (
        <div key={k} className="min-w-0">
          <dt className="text-xs text-faint">{k}</dt>
          <dd className="mt-0.5 break-words text-ink-2">{v ?? "—"}</dd>
        </div>
      ))}
    </dl>
  );
}
