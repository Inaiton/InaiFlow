"use client";

import { Building2, ShieldAlert } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import type { ReactNode } from "react";
import { describeError } from "@/core/api/error-messages";
import { ApiError } from "@/core/api/errors";
import { useAuth } from "@/core/auth/AuthProvider";
import { RequireAuth } from "@/core/auth/RequireAuth";
import { OrgProvider, useResolveOrg } from "@/core/org/OrgProvider";
import { AppShell } from "@/components/shell/AppShell";
import { FullScreenLoader } from "@/components/shell/FullScreenLoader";
import { Button, EmptyState } from "@/components/ui";

function Blocked({ title, description, action }: { title: string; description: string; action?: ReactNode }) {
  return (
    <div className="grid min-h-screen place-items-center bg-canvas p-6">
      <div className="w-full max-w-md">
        <EmptyState icon={ShieldAlert} tone="warning" title={title} description={description} action={action ?? <Button asChild variant="primary"><Link href="/me/organizations">Go to my organizations</Link></Button>} />
      </div>
    </div>
  );
}

function Resolved({ slug, children }: { slug: string; children: ReactNode }) {
  const res = useResolveOrg(slug);
  const { logout } = useAuth();
  if (res.state === "loading") return <FullScreenLoader label="Opening organization…" />;
  if (res.state === "not-member")
    return (
      <div className="grid min-h-screen place-items-center bg-canvas p-6">
        <div className="w-full max-w-md">
          <EmptyState icon={Building2} tone="indigo" title="You’re not a member of this organization" description="Ask an admin to invite you, or request to join with the workspace code."
            action={<Button asChild variant="primary"><Link href="/me/organizations">Go to my organizations</Link></Button>} />
        </div>
      </div>
    );
  if (res.state === "error") {
    const e = res.error;
    if (e instanceof ApiError && e.code === "MFA_REQUIRED")
      return <Blocked title="Two-factor sign-in required" description="This organization requires 2FA. Turn it on in Profile & security, then sign in again."
        action={<div className="flex gap-2"><Button asChild><Link href="/me/security">Set up 2FA</Link></Button><Button variant="primary" onClick={() => void logout()}>Sign in again</Button></div>} />;
    if (e instanceof ApiError && e.code === "ORG_SUSPENDED") return <Blocked title="Organization suspended" description="This organization is suspended. Contact its owner or InaiFlow support." />;
    if (e instanceof ApiError && e.code === "MEMBERSHIP_EXPIRED") return <Blocked title="Your access has expired" description="Your time-bound access to this organization has ended. Ask an admin to extend it." />;
    return <Blocked title="Couldn’t open this organization" description={describeError(e)} />;
  }
  return (
    <OrgProvider value={res.value}>
      <AppShell>{children}</AppShell>
    </OrgProvider>
  );
}

/** `/o/[orgSlug]/*` gate: auth → membership → /org/context → shell. */
export function TenantGate({ children }: { children: ReactNode }) {
  const params = useParams<{ orgSlug: string }>();
  return (
    <RequireAuth>
      <Resolved slug={params.orgSlug}>{children}</Resolved>
    </RequireAuth>
  );
}
