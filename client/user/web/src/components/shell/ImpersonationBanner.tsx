"use client";

import { ShieldAlert } from "lucide-react";
import { useAuth } from "@/core/auth/AuthProvider";
import { formatDateTime } from "@/core/dates";
import { useOrg } from "@/core/org/OrgProvider";
import { Button } from "@/components/ui/button";

/** Yellow bar shown when /org/context reports a support impersonation session. */
export function ImpersonationBanner() {
  const { context } = useOrg();
  const { logout } = useAuth();
  const imp = context.impersonation;
  if (!imp) return null;
  return (
    <div role="status" className="flex flex-wrap items-center gap-3 bg-warning-tint px-5 py-2 text-[13px] text-warning-text">
      <ShieldAlert className="size-4 flex-none" aria-hidden />
      <span className="flex-1">
        <strong>Support session</strong> by {imp.admin_name} · {imp.mode === "READ_ONLY" ? "read-only" : "full support"} · ends {formatDateTime(imp.expires_at)}. Every action is audited.
      </span>
      <Button size="sm" variant="secondary" onClick={() => void logout()}>End session</Button>
    </div>
  );
}
