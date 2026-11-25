---
name: securing-multitenant-rbac
description: Implements and audits multi-tenant PostgreSQL Row-Level Security (RLS), 4-tier RBAC permission checks, record-level ACL overrides, and immutable audit logs. Use whenever touching auth, JWT/session handling, X-Organization-ID, org memberships, roles, permissions, resource_acl, audit logs, or file/storage URLs.
---

# Security & Compliance Checklist

1. **Tenant Isolation (PostgreSQL RLS):** Every tenant-scoped DB transaction in `server` must execute `SET LOCAL ROLE inaiflow_app` and `set_config('app.current_org_id', :org_id, true)` immediately after opening the transaction. Never trust client-supplied `org_id` in request bodies without verifying `org_memberships`. Every new tenant table gets `org_id`, `ENABLE ROW LEVEL SECURITY`, and a `tenant_isolation_<table>` policy.
2. **Middleware Order:** Verify JWT -> validate active `org_memberships` row (and `access_expires_at`) -> enforce org security policy (2FA for externals) -> check RBAC + resource ACL -> set RLS context.
3. **4-Tier RBAC + Resource ACL:** Protect every endpoint with `require_permission("<module>.<subfeature>", min_level="NONE|READ|WRITE|FULL")` (order: `NONE < READ < WRITE < FULL`). When `stock_item_id`, `period_run_id`, or `folder_id` is passed, evaluate `resource_acl` overrides.
4. **External Collaborator Guards:** Enforce `mfa_verified == True` and `access_expires_at > NOW()` for external CAs and guest ISO Auditors.
5. **Immutable Audit Trail:** Decorate all `CREATE`, `UPDATE`, `DELETE`, `APPROVE`, `LOCK`, and `OVERRIDE` service methods (`@audit_log(module=..., action=...)`) to append `before_diff`, `after_diff`, `user_id`, `role_code`, and `reason` to `org_audit_logs`. Never allow `UPDATE` or `DELETE` on audit log tables.
6. **Signed Storage URLs:** Never store or expose public URLs for bills, payslips, or ISO SOPs. Generate short-lived signed URLs after RBAC verification.
7. **Superadmin Isolation:** `platform_admins` authenticate separately from `users`, live only in `client/admin/web`, and every action writes `platform_audit_logs`.

## Reference
- Permission keys (`accounts.*`, `operations.*`, `documents.*`, `organization.*`) and default roles: see the RBAC section in `docs/specs/09_API_CONTRACTS_AND_STATE_MACHINES.md` (section 1) and the `org_roles` / `resource_acl` tables in `docs/specs/06_POSTGRES_DATABASE_SCHEMA.sql` (section 2). Grep for the table you need; don't load the whole file.
