"use client";

import { useQuery } from "@tanstack/react-query";
import { createContext, useContext, useEffect, useMemo, type ReactNode } from "react";
import { api, createOrgClient, unwrap, type OrgClient } from "@/core/api/client";
import { ApiError } from "@/core/api/errors";
import type { Schemas } from "@/core/api/types";
import { useAuth } from "@/core/auth/AuthProvider";
import { writePref } from "@/core/prefs";
import { qk } from "@/core/query-keys";

export type OrgContextOut = Schemas["OrgContextOut"];
export type MyOrgOut = Schemas["MyOrgOut"];

export interface OrgValue {
  orgId: string;
  slug: string;
  context: OrgContextOut;
  /** Org-bound API client (injects X-Organization-ID). */
  api: OrgClient;
  refetchContext: () => void;
}

const OrgCtx = createContext<OrgValue | null>(null);

export const myOrgsQuery = () => ({
  queryKey: qk.me("organizations"),
  queryFn: () => unwrap(api.GET("/api/v1/me/organizations")),
  staleTime: 60_000,
});

export type OrgResolution =
  | { state: "loading" }
  | { state: "not-member" }
  | { state: "error"; error: unknown }
  | { state: "ready"; value: OrgValue };

/** Resolve `/o/[orgSlug]` → membership → `/org/context`. */
export function useResolveOrg(slug: string): OrgResolution {
  const { impersonation } = useAuth();
  const memberships = useQuery({ ...myOrgsQuery(), enabled: !impersonation });

  const orgId = impersonation
    ? (impersonation.orgId ?? undefined)
    : memberships.data?.find((m) => m.workspace_slug === slug)?.org_id;

  const context = useQuery({
    queryKey: qk.org(orgId ?? "-", "org", "context"),
    queryFn: () => unwrap(createOrgClient(orgId!).GET("/api/v1/org/context")),
    enabled: Boolean(orgId),
    staleTime: 60_000,
    retry: (count, err) => !(err instanceof ApiError && err.status >= 400 && err.status < 500) && count < 2,
  });

  if (!impersonation && memberships.isPending) return { state: "loading" };
  if (!impersonation && memberships.isError) return { state: "error", error: memberships.error };
  if (!orgId) return { state: "not-member" };
  if (context.isPending) return { state: "loading" };
  if (context.isError) return { state: "error", error: context.error };
  return {
    state: "ready",
    value: { orgId, slug: context.data.workspace_slug, context: context.data, api: createOrgClient(orgId), refetchContext: () => void context.refetch() },
  };
}

export function OrgProvider({ value, children }: { value: OrgValue; children: ReactNode }) {
  useEffect(() => {
    writePref("lastOrgSlug", value.slug);
  }, [value.slug]);
  const memo = useMemo(() => value, [value]);
  return <OrgCtx.Provider value={memo}>{children}</OrgCtx.Provider>;
}

/** Active organization for tenant routes. Throws outside `/o/[orgSlug]`. */
export function useOrg(): OrgValue {
  const v = useContext(OrgCtx);
  if (!v) throw new Error("useOrg must be used inside a tenant route (/o/[orgSlug])");
  return v;
}

/** Same as useOrg but returns null outside tenant routes (for shared shell pieces). */
export function useOptionalOrg(): OrgValue | null {
  return useContext(OrgCtx);
}
