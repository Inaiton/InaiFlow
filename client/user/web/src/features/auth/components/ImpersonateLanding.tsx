"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { createOrgClient, unwrap } from "@/core/api/client";
import { describeError } from "@/core/api/error-messages";
import { sessionStore } from "@/core/auth/session-store";
import { Hint } from "@/components/ui/feedback";
import { AuthCard } from "@/components/shell/AuthShell";
import { FullScreenLoader } from "@/components/shell/FullScreenLoader";
import { parseImpersonationHash } from "../impersonation";

/**
 * Support impersonation entry: reads `#token=…` from the fragment (never sent to servers or logs),
 * keeps it in memory only, clears the hash, loads the target org and routes into it.
 */
export function ImpersonateLanding() {
  const params = useSearchParams();
  const router = useRouter();
  const ended = params.get("ended") === "1";
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (ended) return;
    const start = async () => {
      const launch = parseImpersonationHash(window.location.hash);
      window.history.replaceState(null, "", window.location.pathname);
      if (!launch) throw new Error("This support link is invalid or was already used. Launch it again from the admin console.");
      if (!launch.orgId) throw new Error("The support link doesn’t say which organization to open.");
      sessionStore.startImpersonation(launch.token, { orgId: launch.orgId, orgSlug: launch.slug });
      const ctx = await unwrap(createOrgClient(launch.orgId).GET("/api/v1/org/context"));
      sessionStore.startImpersonation(launch.token, { orgId: ctx.org_id, orgSlug: ctx.workspace_slug });
      router.replace(`/o/${ctx.workspace_slug}`);
    };
    start().catch((e: unknown) => {
      sessionStore.clear();
      setError(describeError(e));
    });
  }, [ended, router]);

  if (ended)
    return (
      <AuthCard title="Support session ended">
        <Hint tone="gray">The impersonation session has ended or expired. Close this tab or relaunch from the admin console.</Hint>
      </AuthCard>
    );
  if (error)
    return (
      <AuthCard title="Couldn’t start the support session">
        <Hint tone="danger">{error}</Hint>
      </AuthCard>
    );
  return <FullScreenLoader label="Starting support session…" />;
}
