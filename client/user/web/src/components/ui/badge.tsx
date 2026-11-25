import type { HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export type Tone = "success" | "warning" | "danger" | "indigo" | "sky" | "violet" | "teal" | "accent" | "orange" | "gray";

export const TONE_CLASSES: Record<Tone, { tint: string; text: string; solid: string }> = {
  success: { tint: "bg-success-tint", text: "text-success-text", solid: "bg-success" },
  warning: { tint: "bg-warning-tint", text: "text-warning-text", solid: "bg-warning" },
  danger: { tint: "bg-danger-tint", text: "text-danger-text", solid: "bg-danger" },
  indigo: { tint: "bg-indigo-tint", text: "text-indigo-text", solid: "bg-indigo" },
  sky: { tint: "bg-sky-tint", text: "text-sky-text", solid: "bg-sky" },
  violet: { tint: "bg-violet-tint", text: "text-violet-text", solid: "bg-violet" },
  teal: { tint: "bg-teal-tint", text: "text-teal-text", solid: "bg-teal" },
  accent: { tint: "bg-primary-tint", text: "text-primary-text", solid: "bg-primary" },
  orange: { tint: "bg-orange-tint", text: "text-orange-text", solid: "bg-orange" },
  gray: { tint: "bg-gray-tint", text: "text-gray-text", solid: "bg-fg-muted" },
};

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: Tone;
  dot?: boolean;
}

/** Tinted status chip (design `chip()`): rounded-square, 11.5px semibold. */
export function Badge({ tone = "gray", dot, className, children, ...props }: BadgeProps) {
  const t = TONE_CLASSES[tone];
  return (
    <span className={cn("inline-flex items-center gap-1.5 rounded-md px-[7px] py-0.5 text-[11.5px] font-semibold whitespace-nowrap", t.tint, t.text, className)} {...props}>
      {dot ? <span className={cn("size-1.5 rounded-[2px]", t.solid)} aria-hidden /> : null}
      {children}
    </span>
  );
}

/** Map common API status strings to tones. */
export function statusTone(status: string | null | undefined): Tone {
  switch ((status ?? "").toUpperCase()) {
    case "ACTIVE":
    case "APPROVED":
    case "ACCEPTED":
    case "PAID":
    case "COMPLETED":
    case "PASSED":
    case "REGULAR":
      return "success";
    case "PENDING":
    case "INVITED":
    case "TRIAL":
    case "UNDER_REVIEW":
    case "DUE":
    case "QC_HOLD":
      return "warning";
    case "SUSPENDED":
    case "REJECTED":
    case "REVOKED":
    case "EXPIRED":
    case "CANCELLED":
    case "ARCHIVED":
    case "DECLINED":
      return "danger";
    case "DRAFT":
    case "PLANNED":
      return "indigo";
    default:
      return "gray";
  }
}

export const titleCase = (s: string): string =>
  s.toLowerCase().replace(/_/g, " ").replace(/(^|\s)\S/g, (c) => c.toUpperCase());

export function StatusBadge({ status, className }: { status: string | null | undefined; className?: string }) {
  return (
    <Badge tone={statusTone(status)} className={className}>
      {status ? titleCase(status) : "—"}
    </Badge>
  );
}
