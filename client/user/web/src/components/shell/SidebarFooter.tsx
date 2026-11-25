"use client";

import Link from "next/link";
import { useAuth } from "@/core/auth/AuthProvider";
import { formatDate, fyProgress } from "@/core/dates";
import { useOrg } from "@/core/org/OrgProvider";
import { Avatar } from "@/components/ui/icon-tile";

/** FY meter + user chip at the bottom of the tenant sidebar. */
export function SidebarFooter({ collapsed }: { collapsed: boolean }) {
  const { context } = useOrg();
  const { user } = useAuth();
  const fy = context.current_fy;
  const pct = fyProgress(fy);
  const name = user?.full_name ?? context.impersonation?.admin_name ?? "Support";
  if (collapsed) return <div className="flex justify-center"><Avatar name={name} src={user?.avatar_url} /></div>;
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-col gap-2 rounded-2xl border border-line bg-surface px-3.5 py-3">
        <div className="flex items-center justify-between text-xs text-fg-muted">
          <span>Financial year</span>
          <span className="tabular">{pct}%</span>
        </div>
        <span className="text-[13px] font-semibold text-fg">{fy.label}</span>
        <div className="h-1.5 rounded-[3px] bg-line" aria-hidden>
          <div className="h-1.5 rounded-[3px] bg-indigo" style={{ width: `${pct}%` }} />
        </div>
        <span className="text-[11.5px] text-fg-muted">{formatDate(fy.start)} – {formatDate(fy.end)}</span>
      </div>
      <Link href="/me" className="flex items-center gap-2.5 rounded-xl px-1.5 py-1 no-underline hover:bg-subtle">
        <Avatar name={name} src={user?.avatar_url} />
        <span className="flex min-w-0 flex-col">
          <span className="truncate text-[13px] font-semibold text-fg">{name}</span>
          <span className="truncate text-[11.5px] text-fg-muted">{context.role_name}</span>
        </span>
      </Link>
    </div>
  );
}
