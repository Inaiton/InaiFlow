# SUPERADMIN CONSOLE (/superadmin)
## 1. Isolation: platform_admins authenticate separately (mandatory TOTP MFA, IP allowlist), outside tenant RLS. Global statutory rules propagate live with effective-date versioning; master templates seed new orgs and can be pushed as optional updates.
## 2. Routes
* /superadmin dashboard: org counts (active/trial/suspended), users, MRR, active runs, vouchers today, storage, IRP health.
* /superadmin/organizations & /:orgId: directory filter (name, slug, GSTIN, industry, plan, status); lifecycle (activate, extend trial, suspend, archive); plan & quota overrides; owner transfer; audited impersonation (30 min, read-only or full, mandatory ticket reason, logged).
* /superadmin/users: global users, memberships, reset MFA, verify email, suspend.
* /superadmin/global-config: tax-rules (GST slabs, HSN/SAC, cess, e-way thresholds, TDS/TCS sections, payroll statutory, PT slabs, IT slabs); accounting-seeds (28 groups, industry ledgers, UoM, 24 voucher types); iso-workflows (React Flow template editor); doc-templates (report + folder blueprints); rbac-defaults (6 role matrices).
* /superadmin/plans-billing: plans, feature flags (accounts, payroll, operations, documents, tally_xml_sync, irp_einvoice), subscription invoices.
* /superadmin/audit-logs: immutable platform audit trail.
