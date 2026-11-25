/**
 * Explicit empty `header` for mutating tenant calls: the contract declares an optional
 * `Idempotency-Key` header and core `OrgPaths` currently types `params.header` as required
 * (requested fix: docs/plan/requests/W1.md #1). `{ ...H, path }` stays valid after the fix.
 */
export const H = { header: {} } as const;
