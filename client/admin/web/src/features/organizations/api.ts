import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, unwrap, type Schemas } from "@/lib/api/client";

export interface OrgFilters {
  q?: string;
  status?: string;
  plan_code?: string;
  industry?: string;
  limit: number;
  offset: number;
}

export const orgKeys = {
  all: ["admin", "organizations"] as const,
  list: (f: OrgFilters) => ["admin", "organizations", "list", f] as const,
  detail: (id: string) => ["admin", "organizations", "detail", id] as const,
};

const clean = (f: OrgFilters) => ({ ...f, q: f.q || undefined, status: f.status || undefined, plan_code: f.plan_code || undefined, industry: f.industry || undefined });

export function useOrgs(f: OrgFilters) {
  return useQuery({
    queryKey: orgKeys.list(f),
    queryFn: () => unwrap(api.GET("/api/v1/admin/organizations", { params: { query: clean(f) } })),
    placeholderData: keepPreviousData,
  });
}

export function useOrg(id: string) {
  return useQuery({ queryKey: orgKeys.detail(id), queryFn: () => unwrap(api.GET("/api/v1/admin/organizations/{org_id}", { params: { path: { org_id: id } } })) });
}

function useOrgMutation<B>(id: string, fn: (path: { org_id: string }, body: B) => Promise<Schemas["AdminOrgDetail"]>) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: B) => fn({ org_id: id }, body),
    onSuccess: (data) => {
      qc.setQueryData(orgKeys.detail(id), data);
      void qc.invalidateQueries({ queryKey: [...orgKeys.all, "list"] });
    },
  });
}

export function useLifecycle(id: string) {
  return useOrgMutation<Schemas["LifecycleIn"]>(id, (path, body) => unwrap(api.POST("/api/v1/admin/organizations/{org_id}/lifecycle", { params: { path }, body })));
}

export function usePlanChange(id: string) {
  return useOrgMutation<Schemas["PlanChangeIn"]>(id, (path, body) => unwrap(api.PATCH("/api/v1/admin/organizations/{org_id}/plan", { params: { path }, body })));
}

export function useTransferOwner(id: string) {
  return useOrgMutation<Schemas["TransferOwnerIn"]>(id, (path, body) => unwrap(api.POST("/api/v1/admin/organizations/{org_id}/transfer-owner", { params: { path }, body })));
}

export function useImpersonate(id: string) {
  return useMutation({
    mutationFn: (body: Schemas["ImpersonateIn"]) => unwrap(api.POST("/api/v1/admin/organizations/{org_id}/impersonate", { params: { path: { org_id: id } }, body })),
  });
}

export function useOrgMembers(id: string, enabled = true) {
  return useQuery({
    queryKey: [...orgKeys.detail(id), "members"],
    queryFn: () => unwrap(api.GET("/api/v1/admin/organizations/{org_id}/members", { params: { path: { org_id: id } } })),
    enabled,
  });
}
