"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { useAuth } from "@/core/auth/AuthProvider";
import { readPref } from "@/core/prefs";
import { useQuery } from "@tanstack/react-query";
import { myOrgsQuery } from "@/core/org/OrgProvider";
import { FullScreenLoader } from "@/components/shell/FullScreenLoader";

/** `/` → last opened org (if still an active membership) → otherwise personal space; anonymous → /login. */
export default function RootRedirect() {
  const { status, isImpersonating, impersonation } = useAuth();
  const router = useRouter();
  const enabled = status === "authenticated" && !isImpersonating;
  const orgs = useQuery({ ...myOrgsQuery(), enabled });
  useEffect(() => {
    if (status === "anonymous") router.replace("/login");
    else if (isImpersonating && impersonation?.orgSlug) router.replace(`/o/${impersonation.orgSlug}`);
    else if (enabled && orgs.isSuccess) {
      const last = readPref("lastOrgSlug");
      const active = orgs.data.filter((o) => o.membership_status === "ACTIVE");
      const target = active.find((o) => o.workspace_slug === last) ?? (active.length === 1 ? active[0] : undefined);
      router.replace(target ? `/o/${target.workspace_slug}` : "/me/organizations");
    } else if (enabled && orgs.isError) router.replace("/me/organizations");
  }, [status, isImpersonating, impersonation, enabled, orgs.isSuccess, orgs.isError, orgs.data, router]);
  return <FullScreenLoader />;
}
