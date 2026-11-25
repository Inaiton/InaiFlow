/**
 * Query-key conventions (skill: enforcing-modular-architecture rule 8):
 *  - tenant data:   [orgId, domain, ...rest]   e.g. qk.org(orgId, "accounts", "ledgers", { q })
 *  - personal data: ["me", ...rest]
 *  - public meta:   ["meta", ...rest]
 * Invalidate a whole domain with `queryClient.invalidateQueries({ queryKey: qk.org(orgId, "accounts") })`.
 */
export type OrgDomain = "org" | "organization" | "accounts" | "operations" | "documents";

export const qk = {
  org: (orgId: string, domain: OrgDomain, ...rest: unknown[]) => [orgId, domain, ...rest] as const,
  me: (...rest: unknown[]) => ["me", ...rest] as const,
  meta: (...rest: unknown[]) => ["meta", ...rest] as const,
};
