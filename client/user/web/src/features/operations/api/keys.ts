"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useOrg } from "@/core/org/OrgProvider";
import { qk } from "@/core/query-keys";

/** Query keys: [orgId, "operations", ...rest]. */
export function useOpsKey() {
  const { orgId } = useOrg();
  return (...rest: unknown[]) => qk.org(orgId, "operations", ...rest);
}

/** Invalidate operations (optionally also accounts/documents, which runs touch). */
export function useOpsInvalidate() {
  const qc = useQueryClient();
  const { orgId } = useOrg();
  return (opts: { accounts?: boolean; documents?: boolean } = {}) => {
    void qc.invalidateQueries({ queryKey: qk.org(orgId, "operations") });
    if (opts.accounts) void qc.invalidateQueries({ queryKey: qk.org(orgId, "accounts") });
    if (opts.documents) void qc.invalidateQueries({ queryKey: qk.org(orgId, "documents") });
  };
}
