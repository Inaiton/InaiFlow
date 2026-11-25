"use client";

import { useQuery } from "@tanstack/react-query";
import { unwrap } from "@/core/api/client";
import { useOrg } from "@/core/org/OrgProvider";
import { useCan } from "@/core/permissions/Can";
import { qk } from "@/core/query-keys";

/**
 * Read-only lookups into other modules' public endpoints (accounts / organization) used by
 * operations screens. Keys live under the owning domain with an "ops-lookup" segment so
 * the owning stream's invalidations refresh them without colliding with its own keys.
 */
export function useGodowns() {
  const { orgId, api } = useOrg();
  const allowed = useCan("accounts.inventory_masters", "READ");
  return useQuery({
    queryKey: qk.org(orgId, "accounts", "ops-lookup", "godowns"),
    queryFn: () => unwrap(api.GET("/api/v1/accounts/godowns")),
    enabled: allowed,
    staleTime: 300_000,
  });
}

export function useLedgerLookup(q: string, enabled = true) {
  const { orgId, api } = useOrg();
  const allowed = useCan("accounts.ledgers_groups", "READ");
  return useQuery({
    queryKey: qk.org(orgId, "accounts", "ops-lookup", "ledgers", q),
    queryFn: () => unwrap(api.GET("/api/v1/accounts/ledgers", { params: { query: { q: q || undefined, limit: 30, offset: 0 } } })),
    enabled: allowed && enabled,
    placeholderData: (prev) => prev,
  });
}

export function useVoucherLookup(q: string, enabled = true) {
  const { orgId, api } = useOrg();
  const allowed = useCan("accounts.vouchers", "READ");
  return useQuery({
    queryKey: qk.org(orgId, "accounts", "ops-lookup", "vouchers", q),
    queryFn: () => unwrap(api.GET("/api/v1/accounts/vouchers", { params: { query: { q: q || undefined, status: "REGULAR", limit: 30, offset: 0 } } })),
    enabled: allowed && enabled,
    placeholderData: (prev) => prev,
  });
}

export function useRoleLookup() {
  const { orgId, api } = useOrg();
  const allowed = useCan("organization.roles_rbac", "READ");
  return useQuery({
    queryKey: qk.org(orgId, "organization", "ops-lookup", "roles"),
    queryFn: () => unwrap(api.GET("/api/v1/organization/roles")),
    enabled: allowed,
    staleTime: 300_000,
  });
}

export function useMemberLookup() {
  const { orgId, api } = useOrg();
  const allowed = useCan("organization.members", "READ");
  return useQuery({
    queryKey: qk.org(orgId, "organization", "ops-lookup", "members"),
    queryFn: () => unwrap(api.GET("/api/v1/organization/members", { params: { query: { status: "ACTIVE" } } })),
    enabled: allowed,
    staleTime: 300_000,
  });
}
