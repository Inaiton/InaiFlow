import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export type Tone = "success" | "warning" | "danger" | "indigo" | "sky" | "violet" | "teal" | "accent" | "orange" | "gray";

const tones: Record<Tone, string> = {
  success: "bg-success-tint text-success-ink",
  warning: "bg-warning-tint text-warning-ink",
  danger: "bg-danger-tint text-danger-ink",
  indigo: "bg-indigo-tint text-indigo",
  sky: "bg-sky-tint text-[#026AA2]",
  violet: "bg-violet-tint text-[#5925DC]",
  teal: "bg-teal-tint text-[#107569]",
  accent: "bg-primary-tint text-primary-hover",
  orange: "bg-orange-tint text-[#B93815]",
  gray: "bg-subtle text-[#344054]",
};

export function Badge({ tone = "gray", children, className }: { tone?: Tone; children: ReactNode; className?: string }) {
  return <span className={cn("inline-flex items-center gap-1 rounded-sm px-1.5 py-0.5 text-xs font-medium", tones[tone], className)}>{children}</span>;
}

const STATUS_TONES: Record<string, Tone> = {
  ACTIVE: "success",
  PAID: "success",
  OK: "success",
  HEALTHY: "success",
  TRIAL: "warning",
  DUE: "warning",
  DEGRADED: "warning",
  PENDING: "warning",
  SUSPENDED: "danger",
  DOWN: "danger",
  ERROR: "danger",
  ARCHIVED: "gray",
  VOID: "gray",
  INACTIVE: "gray",
};

export function StatusBadge({ status }: { status: string | null | undefined }) {
  const s = (status ?? "—").toUpperCase();
  const label = s.charAt(0) + s.slice(1).toLowerCase().replace(/_/g, " ");
  return <Badge tone={STATUS_TONES[s] ?? "gray"}>{label}</Badge>;
}
