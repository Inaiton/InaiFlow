import { cn } from "@/lib/utils";

export function envTone(env: string | null | undefined): string {
  const e = (env ?? "").toUpperCase();
  if (e.startsWith("PROD")) return "bg-danger text-white";
  if (e.startsWith("STAG")) return "bg-warning text-white";
  return "bg-faint text-white";
}

export function EnvBadge({ env, className }: { env: string | null | undefined; className?: string }) {
  const label = (env ?? "UNKNOWN").toUpperCase();
  const normalized = label.startsWith("PROD") ? "PRODUCTION" : label.startsWith("STAG") ? "STAGING" : label.startsWith("DEV") || label === "LOCAL" ? "DEVELOPMENT" : label;
  return <span className={cn("rounded-sm px-2 py-0.5 text-[11px] font-bold tracking-wider", envTone(env), className)}>{normalized}</span>;
}
