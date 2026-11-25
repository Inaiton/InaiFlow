"use client";

import { useQuery } from "@tanstack/react-query";
import { unwrap } from "@/core/api/client";
import { useOrg } from "@/core/org/OrgProvider";
import { useCan } from "@/core/permissions/Can";
import { qk } from "@/core/query-keys";
import type { SelectOption } from "@/components/ui";
import { useMembers } from "../api";

/**
 * Role choices for invite / approve / role-change. Uses GET /organization/roles when the user can read
 * roles; otherwise falls back to the roles seen on current members. The owner role is never offered.
 */
export function useRoleOptions(): { options: SelectOption[]; loading: boolean } {
  const { api, orgId } = useOrg();
  const canReadRoles = useCan("organization.roles_rbac", "READ");
  const roles = useQuery({
    queryKey: qk.org(orgId, "organization", "roles"),
    queryFn: () => unwrap(api.GET("/api/v1/organization/roles")),
    enabled: canReadRoles,
    meta: { silentError: true },
  });
  const members = useMembers();
  if (canReadRoles && roles.data)
    return {
      options: roles.data.filter((r) => r.role_code !== "ORG_OWNER").map((r) => ({ value: r.id, label: r.role_name, hint: r.is_external_collaborator ? "External collaborator" : undefined })),
      loading: false,
    };
  const seen = new Map<string, SelectOption>();
  for (const m of members.data ?? []) if (!m.is_owner) seen.set(m.role_id, { value: m.role_id, label: m.role_name });
  return { options: [...seen.values()], loading: roles.isPending || members.isPending };
}
