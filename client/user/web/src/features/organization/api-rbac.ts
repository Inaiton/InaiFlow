"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api as publicApi, unwrap } from "@/core/api/client";
import type { Schemas } from "@/core/api/types";
import { useOrg } from "@/core/org/OrgProvider";
import { qk } from "@/core/query-keys";

/** Roles, ACL, security, audit logs, billing hooks. */
function useKeys() {
  const { orgId } = useOrg();
  const qc = useQueryClient();
  return {
    key: (...rest: unknown[]) => qk.org(orgId, "organization", ...rest),
    inv: (...rest: unknown[]) => qc.invalidateQueries({ queryKey: qk.org(orgId, "organization", ...rest) }),
  };
}

export const usePermissionKeys = () =>
  useQuery({ queryKey: qk.meta("permission-keys"), queryFn: () => unwrap(publicApi.GET("/api/v1/meta/permission-keys")), staleTime: Infinity });

export function useRoles() {
  const { api } = useOrg();
  const { key } = useKeys();
  return useQuery({ queryKey: key("roles"), queryFn: () => unwrap(api.GET("/api/v1/organization/roles")) });
}

export function useCreateRole() {
  const { api } = useOrg();
  const { inv } = useKeys();
  return useMutation({
    mutationFn: (body: Schemas["RoleIn"]) => unwrap(api.POST("/api/v1/organization/roles", { body })),
    onSuccess: () => inv("roles"),
    meta: { successMessage: "Role created" },
  });
}

export function useUpdateRole() {
  const { api, refetchContext } = useOrg();
  const { inv } = useKeys();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: Schemas["RoleUpdateIn"] }) =>
      unwrap(api.PATCH("/api/v1/organization/roles/{role_id}", { params: { path: { role_id: id } }, body })),
    onSuccess: () => {
      void inv("roles");
      refetchContext();
    },
    meta: { successMessage: "Role saved" },
  });
}

export function useDeleteRole() {
  const { api } = useOrg();
  const { inv } = useKeys();
  return useMutation({
    mutationFn: (role_id: string) => unwrap(api.DELETE("/api/v1/organization/roles/{role_id}", { params: { path: { role_id } } })),
    onSuccess: () => inv("roles"),
    meta: { successMessage: "Role deleted" },
  });
}

export function useAcl(query: { subject_type?: string; resource_type?: string } = {}) {
  const { api } = useOrg();
  const { key } = useKeys();
  return useQuery({ queryKey: key("acl", query), queryFn: () => unwrap(api.GET("/api/v1/organization/acl", { params: { query } })) });
}

export function usePutAcl() {
  const { api } = useOrg();
  const { inv } = useKeys();
  return useMutation({
    mutationFn: (body: Schemas["AclIn"]) => unwrap(api.PUT("/api/v1/organization/acl", { body })),
    onSuccess: () => inv("acl"),
    meta: { successMessage: "Override saved" },
  });
}

export function useDeleteAcl() {
  const { api } = useOrg();
  const { inv } = useKeys();
  return useMutation({
    mutationFn: (acl_id: string) => unwrap(api.DELETE("/api/v1/organization/acl/{acl_id}", { params: { path: { acl_id } } })),
    onSuccess: () => inv("acl"),
    meta: { successMessage: "Override removed" },
  });
}

export function useSecuritySettings() {
  const { api } = useOrg();
  const { key } = useKeys();
  return useQuery({ queryKey: key("security"), queryFn: () => unwrap(api.GET("/api/v1/organization/security")) });
}

export function useSaveSecurity() {
  const { api } = useOrg();
  const { inv } = useKeys();
  return useMutation({
    mutationFn: (body: Schemas["SecuritySettings"]) => unwrap(api.PUT("/api/v1/organization/security", { body })),
    onSuccess: () => inv("security"),
    meta: { successMessage: "Security settings saved" },
  });
}

export type AuditQuery = { module?: string; action?: string; entity_type?: string; user_id?: string; date_from?: string; date_to?: string; limit: number; offset: number };

export function useAuditLogs(query: AuditQuery) {
  const { api } = useOrg();
  const { key } = useKeys();
  return useQuery({ queryKey: key("audit-logs", query), queryFn: () => unwrap(api.GET("/api/v1/organization/audit-logs", { params: { query } })), placeholderData: (prev) => prev });
}

export function useBilling() {
  const { api } = useOrg();
  const { key } = useKeys();
  return useQuery({ queryKey: key("billing"), queryFn: () => unwrap(api.GET("/api/v1/organization/billing")) });
}
