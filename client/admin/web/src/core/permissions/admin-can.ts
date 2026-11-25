import { ADMIN_OPERATION_ROLES, type AdminOperation } from "@/lib/api/admin-roles.gen";
import type { components } from "@/lib/api/schema";

export type AdminRole = components["schemas"]["AdminRole"];

/**
 * Action refinements that are narrower than the endpoint's role list (plan §3.3):
 * SUPPORT_ADMIN may run lifecycle actions except ARCHIVE.
 */
const REFINEMENTS = {
  "org.lifecycle.ACTIVATE": "POST /admin/organizations/{org_id}/lifecycle",
  "org.lifecycle.SUSPEND": "POST /admin/organizations/{org_id}/lifecycle",
  "org.lifecycle.EXTEND_TRIAL": "POST /admin/organizations/{org_id}/lifecycle",
  "org.lifecycle.ARCHIVE": ["SUPERADMIN"],
} as const satisfies Record<string, AdminOperation | readonly AdminRole[]>;

export type AdminAction = AdminOperation | keyof typeof REFINEMENTS;

function rolesFor(action: AdminAction): readonly string[] {
  if (action in REFINEMENTS) {
    const r = REFINEMENTS[action as keyof typeof REFINEMENTS];
    return typeof r === "string" ? ADMIN_OPERATION_ROLES[r] : r;
  }
  return ADMIN_OPERATION_ROLES[action as AdminOperation];
}

/** Single source for role-aware UI. Derived from contract `admin <ROLES>` lists (generated). */
export function adminCan(role: AdminRole | null | undefined, action: AdminAction): boolean {
  if (!role) return false;
  const roles = rolesFor(action);
  return roles.includes("ANY") || roles.includes(role);
}
