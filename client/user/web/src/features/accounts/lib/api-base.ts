"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useOrg } from "@/core/org/OrgProvider";
import { qk } from "@/core/query-keys";

/** Shared plumbing for accounts hooks: org client + `[orgId, "accounts", ...]` keys + invalidation. */
export function useAcc() {
  const org = useOrg();
  const qc = useQueryClient();
  const key = (...rest: unknown[]) => qk.org(org.orgId, "accounts", ...rest);
  const invalidate = (...rest: unknown[]) => qc.invalidateQueries({ queryKey: qk.org(org.orgId, "accounts", ...rest) });
  return { ...org, qc, key, invalidate };
}

/** `/o/<slug>/accounts<path>` */
export function useAccHref() {
  const { slug } = useOrg();
  return (path = "") => `/o/${slug}/accounts${path}`;
}

