"use client";

import { LogOut, Search } from "lucide-react";
import { useAuth } from "@/core/auth/AuthProvider";
import { useSystemHealth } from "@/features/system/api";
import { Button } from "@/components/ui/button";
import { EnvBadge } from "./EnvBadge";

const ROLE_LABEL: Record<string, string> = { SUPERADMIN: "Super admin", SUPPORT_ADMIN: "Support admin", BILLING_ADMIN: "Billing admin" };

export function Topbar({ onOpenPalette }: { onOpenPalette: () => void }) {
  const { admin, signOut } = useAuth();
  const health = useSystemHealth();
  const initials = (admin?.full_name ?? "?")
    .split(/\s+/)
    .map((p) => p[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
  return (
    <header className="flex h-14 shrink-0 items-center gap-3 border-b border-line bg-white px-5">
      <EnvBadge env={health.data?.environment ?? (health.isPending ? "…" : "UNKNOWN")} />
      <span className="text-[13px] text-faint">Superadmin</span>
      <button
        type="button"
        onClick={onOpenPalette}
        className="ml-4 flex h-8 w-72 items-center gap-2 rounded-md border border-line bg-canvas px-2.5 text-[13px] text-faint hover:border-faint/40"
      >
        <Search className="size-4" /> Jump to…
        <kbd className="ml-auto rounded-sm border border-line bg-white px-1 text-[11px]">Alt G</kbd>
      </button>
      <div className="ml-auto flex items-center gap-3">
        <div className="flex items-center gap-2">
          <span className="flex size-8 items-center justify-center rounded-md bg-sidebar text-xs font-semibold text-white">{initials}</span>
          <div className="leading-tight">
            <div className="text-[13px] font-medium text-ink">{admin?.full_name}</div>
            <div className="text-[11px] text-faint">{ROLE_LABEL[admin?.role ?? ""] ?? admin?.role}</div>
          </div>
        </div>
        <Button variant="ghost" size="sm" onClick={() => void signOut()} aria-label="Sign out">
          <LogOut /> Sign out
        </Button>
      </div>
    </header>
  );
}
