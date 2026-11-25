"use client";

import { useQuery } from "@tanstack/react-query";
import { unwrap } from "@/core/api/client";
import { useOrg } from "@/core/org/OrgProvider";
import { useCan } from "@/core/permissions/Can";
import { qk } from "@/core/query-keys";

/**
 * Report context lookups (runs, steps, items) read through the operations HTTP API — the
 * documents feature never imports operations code. Keys live under "operations" so run
 * updates refresh them.
 */
export function useRunOptions(q: string, status?: "IN_PROGRESS") {
  const { orgId, api } = useOrg();
  const allowed = useCan("operations.runs_execution", "READ");
  return useQuery({
    queryKey: qk.org(orgId, "operations", "doc-lookup", "runs", q, status ?? "any"),
    queryFn: () => unwrap(api.GET("/api/v1/operations/runs", { params: { query: { q: q || undefined, status, limit: 20, offset: 0 } } })),
    enabled: allowed,
    placeholderData: (prev) => prev,
  });
}

export function useRunContext(runId: string | null) {
  const { orgId, api } = useOrg();
  const allowed = useCan("operations.runs_execution", "READ");
  return useQuery({
    queryKey: qk.org(orgId, "operations", "run", runId),
    queryFn: () => unwrap(api.GET("/api/v1/operations/runs/{run_id}", { params: { path: { run_id: runId! } } })),
    enabled: allowed && Boolean(runId),
  });
}

export function useItemOptions(q: string) {
  const { orgId, api } = useOrg();
  const allowed = useCan("operations.items", "READ");
  return useQuery({
    queryKey: qk.org(orgId, "operations", "doc-lookup", "items", q),
    queryFn: () => unwrap(api.GET("/api/v1/operations/items", { params: { query: { q: q || undefined, limit: 20, offset: 0 } } })),
    enabled: allowed,
    placeholderData: (prev) => prev,
  });
}
