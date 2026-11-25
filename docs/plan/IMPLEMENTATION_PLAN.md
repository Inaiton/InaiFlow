# InaiFlow — Implementation Plan (v1)

Status: approved baseline for the first full build. Every agent and contributor MUST read this file, `CLAUDE.md`,
and the API contract (`docs/api/contract.api` → generated `docs/api/openapi.json`) before writing code.
The contract is the single source of truth for every HTTP endpoint, payload and permission. Changing an endpoint
means changing `docs/api/contract.api` first, regenerating, and updating server + both clients in the same change.

---

## 1. Repository layout (only three major items)

```
client/
  user/web/        Next.js tenant app      (package: @inaiflow/user-web)   → Vercel project "inaiflow-user-web"
  admin/web/       Next.js superadmin app  (package: @inaiflow/admin-web)  → Vercel project "inaiflow-admin-web"
server/            FastAPI modular monolith (Python 3.12, uv)              → Vercel project "inaiflow-server"
docs/
  specs/           product specs (00–09)
  plan/            this plan
  api/             contract.api (DSL), openapi.json (generated), gen_openapi.py
.github/workflows/ CI (lint, typecheck, tests, contract check)
package.json, pnpm-workspace.yaml   (workspace = client/*/web)
```

No shared TS package is created (keeps the three-item rule). Each web app owns its UI kit under
`src/components/ui` and generates its typed API client from `docs/api/openapi.json` into
`src/lib/api/schema.d.ts` (`pnpm gen:api`). Nobody hand-writes payload types.

## 2. Stack (pinned majors)

| Layer | Choice |
|---|---|
| Web | Next.js 16 App Router, React 19, TypeScript strict, Tailwind v4, shadcn/ui (Radix), TanStack Query 5 + Table 8, zod 4 + react-hook-form, `openapi-fetch` + `openapi-typescript`, `@xyflow/react` (loaded with `next/dynamic`, no SSR), `cmdk` (Alt+G palette), `sonner` toasts, `lucide-react` icons |
| Server | Python 3.12, FastAPI, SQLAlchemy 2 async + asyncpg, Pydantic v2, Alembic, argon2-cffi, PyJWT, pyotp, cryptography (Fernet), httpx, fpdf2 (PDF), python-docx (DOCX), ofxparse-free in-house parsers |
| Data | Supabase Postgres 17 with RLS (local/dev/test: any Postgres ≥ 15), Supabase Storage private buckets |
| Tooling | uv, ruff, pytest + pytest-asyncio, import-linter; pnpm, eslint, `tsc --noEmit`, Playwright (smoke) |
| Deploy | 3 Vercel projects + 1 Supabase project; Vercel Cron for daily jobs |

## 3. Cross-cutting decisions (non-negotiable)

### 3.1 HTTP conventions
- Base path `/api/v1`. JSON only (except file downloads and multipart imports).
- Tenant routes require `Authorization: Bearer <access>` **and** `X-Organization-ID: <uuid>`.
  Personal routes (`/auth/*`, `/me/*`, `POST /organizations`) never take the org header.
  Admin routes live under `/api/v1/admin/*` with a separate token audience.
- Money, quantities, rates: JSON **strings** matching `^-?\d+(\.\d{1,4})?$` (Pydantic `Decimal` serialized as str).
  Never floats anywhere (server, DB, client math uses string → `Decimal`/`big.js`-free integer-paise helpers in `src/lib/money.ts`).
- Dates `YYYY-MM-DD`; timestamps ISO-8601 UTC with `Z`. Months are passed as `YYYY-MM` query strings or first-of-month dates in bodies.
- Lists: `?limit=50&offset=0` (max 200) → `{items, total, limit, offset}`.
- Errors: HTTP status + body `{"error": {"code": "SNAKE_UPPER", "message": "human text", "details": {...}|null}}`.
  Codes used across the app are enumerated in contract `enum ErrorCode`. Status map:
  400 validation/domain rule, 401 unauthenticated, 403 forbidden/permission/MFA-required, 404 not found
  (also used for cross-tenant access — never leak existence), 409 conflict/state, 413 too large, 422 Pydantic validation,
  423 locked (locked step/period), 429 rate limited.
- Every mutating tenant endpoint accepts optional `Idempotency-Key` header (stored 24h per org+user+key) — required for voucher create and step execute in the web client.

### 3.2 Authentication (user)
- Own auth (no Supabase Auth). `users.password_hash` = argon2id (time_cost 3, memory 64 MiB). Password policy: 10–128 chars, not equal to email, not in a bundled top-10k list.
- Access token: JWT HS256, 15 min, `iss=inaiflow`, `aud=inaiflow-user`, claims `sub, sid, email, mfa (bool), typ="access"`, optional `imp` (impersonation).
- Refresh token: 256-bit random, stored as SHA-256 in `user_sessions`, rotated on every refresh; reuse of a rotated token revokes the whole family. Cookie `if_rt`: HttpOnly, Secure (except localhost), SameSite=Strict, Path=`/api/v1/auth`, 14 days (30 if "remember").
- Web apps call the API through a same-origin Next.js rewrite (`/api/v1/*` → `SERVER_URL`), so cookies are first-party. `POST /auth/refresh` additionally requires header `X-Requested-With: inaiflow` (CSRF).
- Email verification + password reset: 6-digit codes, SHA-256 hashed in `auth_one_time_codes`, 10 min TTL, 5 attempts.
- TOTP MFA (pyotp, 30s, ±1 window); secret encrypted with Fernet (`MFA_ENCRYPTION_KEY`); 10 one-time recovery codes (argon2 hashed).
  Login with MFA enabled returns `MFA_REQUIRED` + 5-min `mfa_token` (JWT `typ="mfa"`); tokens issued after `/auth/mfa/verify` have `mfa=true`.
- Brute force: `auth_login_attempts`; >5 failures per email in 15 min or >20 per IP → 429 for 15 min. Generic error messages (no user enumeration); signup for an existing email returns the same 201 shape and emails the owner instead.
- Google OAuth (OIDC code + PKCE, state cookie) behind `GOOGLE_CLIENT_ID`; disabled → endpoints return 404.

### 3.3 Authentication (platform admin)
- Separate table `platform_admins`, separate secret `ADMIN_JWT_SECRET`, `aud=inaiflow-admin`, cookie `if_art` (Path `/api/v1/admin/auth`).
- MFA is mandatory: first login returns `MFA_SETUP_REQUIRED` with otpauth URI; never issues tokens without TOTP.
- Optional IP allowlist `ADMIN_IP_ALLOWLIST` (comma CIDRs) checked on every `/admin/*` request using `x-vercel-forwarded-for` → `x-forwarded-for` → peer.
- Admin roles: `SUPERADMIN` (everything), `SUPPORT_ADMIN` (orgs/users read, lifecycle except ARCHIVE, impersonation, user actions), `BILLING_ADMIN` (plans, billing, org plan changes, read orgs).
- Bootstrap: `uv run python -m app.cli create-superadmin --email ... --name ...` (prints one-time password).
- Every admin mutation writes `platform_audit_logs` (before/after JSON, IP).

### 3.4 Tenant request pipeline (order matters)
1. Verify access JWT (`aud`, `exp`, `typ=access`), load `user_sessions` row not revoked (cached per request).
2. Load `org_memberships` (org_id from header, user, `status='ACTIVE'`, `access_expires_at` null or future) + role + org (`org_status` not SUSPENDED/ARCHIVED → 403 `ORG_SUSPENDED`).
3. Security policy: if role `is_external_collaborator` and `security_settings.enforce_2fa_external` (or `enforce_2fa_all`) and token `mfa=false` → 403 `MFA_REQUIRED`.
4. `require_permission(key, level)` dependency: effective level = role.permissions[key] (missing → NONE). `ORG_OWNER` is always FULL. Resource ACL: when the route targets a STOCK_ITEM / PERIOD_RUN / DOC_FOLDER / GODOWN, a `resource_acl` row for the USER (wins) or ROLE replaces the module level for that resource (can raise or lower). List endpoints filter out resources whose effective level is NONE.
5. Open DB transaction: `SET LOCAL ROLE inaiflow_app; SELECT set_config('app.current_org_id', :org, true); SELECT set_config('app.current_user_id', :user, true);`.
- Impersonation tokens (`imp` claim) skip membership lookup, act with role `SUPPORT_IMPERSONATION` (READ_ONLY: all keys READ; FULL_SUPPORT: all keys FULL except `organization.billing`, `organization.roles_rbac`, `organization.members`), and every request is written to `platform_audit_logs`.

### 3.5 Row-Level Security
- Role `inaiflow_app` NOLOGIN NOBYPASSRLS; the connection user is granted membership. All tenant tables: `ENABLE` + `FORCE ROW LEVEL SECURITY`, policy
  `tenant_isolation_<table> FOR ALL TO inaiflow_app USING (org_id = current_setting('app.current_org_id', true)::uuid) WITH CHECK (same)`.
- Platform/identity code paths (auth, `/me`, admin, cron) run as the connection user (no `SET ROLE`) and must filter explicitly.
- `REVOKE ALL ... FROM anon, authenticated` (if those Supabase roles exist) so the Supabase Data API can never read tables.
- `org_audit_logs` and `platform_audit_logs`: `inaiflow_app` gets `SELECT, INSERT` only + trigger raising on UPDATE/DELETE (append-only).
- Tests prove: org A cannot read/write org B rows even with forged IDs (RLS test suite).

### 3.6 Server architecture (skill: enforcing-modular-architecture)
```
server/
  pyproject.toml  uv.lock  alembic.ini  vercel.json  .importlinter
  api/index.py                    # Vercel entry: from app.main import app
  app/
    main.py                       # create_app(): routers, middleware, exception handlers, /openapi.json
    cli.py                        # create-superadmin, seed-configs, run-cron
    core/  config.py db.py security.py (jwt, passwords, tokens) crypto.py errors.py deps.py
           (Principal, OrgContext, get_db, get_tenant_db, require_permission, require_admin)
           audit.py (audit_log decorator + write_audit) sequences.py (org_sequences) pagination.py
           money.py (Decimal helpers, quantize) idempotency.py ratelimit.py fy.py (financial-year math)
           events.py (in-process sync domain events) emailer interfaces live in adapters
    adapters/ storage.py (StorageProvider: SupabaseStorage, LocalStorage) email.py (Console, Resend)
              export.py (DocumentExportProvider: Fpdf + Docx) taxgateway.py (TaxGatewayProvider: SandboxIRP, Mock)
    seeds/   account_groups.py default_ledgers.py voucher_types.py roles.py iso_workflows.py doc_templates.py
             folder_templates.py tax_rules.py iso_checklist.py uom.py states.py  (pure data, loaded into
             platform_global_configs by migration 0001 data step / `cli seed-configs`)
    modules/<domain>/ router.py schemas.py service.py repository.py models.py interface.py [events.py] tests/
      identity       auth, me, sessions, mfa
      organization   create org (seeding orchestration), profile, branches, members, invitations, join requests, security, billing view, audit-log read
      rbac           roles, permission resolution, resource ACL
      accounts       groups, ledgers, cost centres, voucher types, currencies, godowns, stock groups/items, vouchers, inventory valuation, banking, reports, dashboard, settings
      taxation       GST (computation, GSTR-1/3B, 2B recon, validation), e-invoice/e-way (adapter), TDS/TCS
      payroll        employees, attendance, payroll settings, runs, lock, payslips, statutory files
      operations     items facade, workflows, runs, steps, money flow, dossier, NCR/CAPA, calibration, ISO checklist, dashboard
      documents      folders, documents, uploads, ISO approval, templates, rendering, search
      superadmin     admin auth, dashboard, orgs, users, configs, plans, billing, impersonation, platform audit
      platform       meta (states, permission keys), health, cron
  migrations/versions/0001_baseline.py … (fixed chain, see §6)
  tests/  conftest.py (Postgres per-session DB, factories), test_rls.py, test_contract.py
```
- Router → Service → Repository. Services own transactions (`async with session.begin()` via `UnitOfWork`), raise domain errors (`app.core.errors`), never `HTTPException`.
- Cross-module calls only through `modules/<x>/interface.py` (import-linter contract enforces: modules may import `app.core`, `app.adapters`, `app.seeds`, and other modules' `interface` only).
- Required interfaces (signatures are binding):
  - `accounts.interface`: `post_system_voucher(db, ctx, *, base_type, voucher_date, entries: list[SystemEntry], inventory: list[SystemInventory]=[], narration, linked_period_run_id=None, linked_step_id=None, status="REGULAR") -> UUID`;
    `create_cost_centre(db, ctx, *, name, linked_period_run_id) -> UUID`; `get_ledger_ids_by_code(db, ctx, codes: list[str]) -> dict[str, UUID]` (system ledger codes, see seeds);
    `get_system_godown_ids(db, ctx) -> dict[str, UUID]` (keys MAIN, WIP, SCRAP, FG); `get_stock_item(db, ctx, item_id) -> StockItemDTO`; `list_vouchers_for_run(db, ctx, run_id) -> list[VoucherDTO]`; `link_voucher_to_run(...)`; `seed_org_accounts(db, ctx, industry_type)`.
  - `documents.interface`: `ensure_month_folders(db, ctx, month: date) -> MonthFolders` (ids of month root + 3 system subfolders + custom), `create_run_folder(db, ctx, *, run_id, run_title, month) -> UUID`, `store_generated_file(db, ctx, *, folder_id, title, mime, data: bytes, source_type, links...) -> UUID`, `seed_org_documents(db, ctx)`, `get_document(db, ctx, id)`.
  - `operations.interface`: `seed_org_operations(db, ctx)`, `get_runs_by_ids(...)`, `apply_payroll_allocation(db, ctx, run_id, amount)`, `list_step_executions_by_month(db, ctx, month)`.
  - `rbac.interface`: `seed_org_roles(db, ctx) -> dict[role_code, role_id]`, `effective_level(...)`, `resource_levels(...)`.
  - `payroll.interface`: `seed_org_payroll(db, ctx)`.
  - `superadmin.interface` / `platform` config access: `get_config(db, category, key, on_date=None) -> dict` (effective-dated).
- Audit: `@audited(module="ACCOUNTS", action="CREATE", entity="voucher")` on service methods or explicit `await write_audit(...)` with before/after dicts (Decimal → str).

### 3.7 Schema
Baseline = `docs/specs/06_POSTGRES_DATABASE_SCHEMA.sql` **plus** the additions below (all tenant tables get org_id + RLS):
- Identity: `user_sessions(id, user_id, family_id, token_hash UNIQUE, user_agent, ip, remember, created_at, last_used_at, expires_at, revoked_at, replaced_by_id)`,
  `admin_sessions` (same shape, admin_id), `auth_one_time_codes(id, subject_type USER|ADMIN, subject_id, email, purpose EMAIL_VERIFY|PASSWORD_RESET, code_hash, attempts, expires_at, consumed_at, created_at)`,
  `user_mfa_recovery_codes(id, user_id, code_hash, used_at)`, `auth_login_attempts(id, email, ip, success, created_at)`, `idempotency_keys(org_id, user_id, key, request_hash, response_status, response_body, created_at, PK(org_id,user_id,key))`.
  `users`: add `avatar_storage_key`, `signature_storage_key`, `last_login_at`. `platform_admins`: add `mfa_enabled`, `must_change_password`.
- Organization: `org_branches(id, org_id, name, address, state_code, gstin, is_head_office)`, `org_sequences(org_id, seq_key, next_value, PK)`;
  `organizations`: add `trial_ends_at`, `quota_overrides JSONB '{}'`, `accounts_settings JSONB '{}'` (books_locked_until, invoice settings), `logo_storage_key`, `stamp_storage_key`.
  `org_invitations_and_requests`: add `message`, `acl_grants JSONB` (auditor scoping), `decided_by`, `decided_at`.
  `org_audit_logs`: `user_id` nullable, add `actor_type USER|SYSTEM|PLATFORM_ADMIN`, `actor_id`.
- Accounts: `stock_groups(id, org_id, name, parent_id)`, `stock_items.stock_group_id`, `stock_items.diagram_storage_key`; `ledgers.system_code` (e.g. `CASH`, `SALES`, `PURCHASE`, `CGST_OUT`, `SGST_OUT`, `IGST_OUT`, `CGST_IN`, `SGST_IN`, `IGST_IN`, `RCM_PAYABLE`, `ROUND_OFF`, `TDS_PAYABLE`, `TCS_PAYABLE`, `SALARY_PAYABLE`, `DIRECT_WAGES`, `ADMIN_SALARIES`, `EMPLOYER_PF_ESIC`, `EPF_PAYABLE`, `ESIC_PAYABLE`, `PT_PAYABLE`, `SALARY_TDS_PAYABLE`, `SCRAP_RECOVERY`, `MFG_OVERHEAD`, `STOCK_FG`, `STOCK_RM`, `STOCK_WIP`, `STOCK_SCRAP`, `FOREX_GAIN_LOSS`) unique per org;
  `account_groups.system_code`; `voucher_types.is_accounting`, `voucher_types.shortcut`, `voucher_types.is_system`; `vouchers.cancel_reason`, `vouchers.cancelled_at`, `vouchers.idempotency_key`;
  `currencies(id, org_id, code, symbol, name, decimal_places)`, `exchange_rates(id, org_id, currency_code, rate_date, rate_to_base)`;
  `cheque_books(id, org_id, bank_ledger_id, from_number, to_number, next_number, created_at)`;
  `bank_statement_imports(id, org_id, bank_ledger_id, file_name, format, imported_by, line_count, created_at)`,
  `bank_statement_lines(id, org_id, import_id, bank_ledger_id, txn_date, value_date, description, reference, debit, credit, balance, matched_entry_id, status UNMATCHED|MATCHED|IGNORED)`;
  `gst_2b_imports(id, org_id, period YYYY-MM, payload JSONB, imported_by, created_at)`; `einvoice_records(id, org_id, voucher_id, kind IRN|EWAY, status, irn, ack_no, ack_date, signed_qr, eway_bill_no, valid_until, raw JSONB, created_at)`.
- Payroll: `payroll_settings` as `organizations.accounts_settings.payroll` is NOT used — table `payroll_settings(org_id PK, pt_state_code, ledger mapping columns..., updated_at)`; `payroll_attendance(id, org_id, month, employee_id, days_present, lop_days, overtime_hours, production_units, run_allocations JSONB, finalized, UNIQUE(org_id, month, employee_id))`.
- Operations: `workflow_templates`: add `template_key UUID` (version family), `description`, `status DRAFT|PUBLISHED|ARCHIVED`, `published_at`, `UNIQUE(org_id, template_key, version)`;
  `period_runs`: add `graph_snapshot JSONB`, `started_at`, `cancel_reason`, `hold_reason`, `mfg_voucher_id`;
  `period_run_steps`: add `sequence INT`, `rework_qty`, `executed_by`, `executed_at`, `notes`, `instrument_id`, `skip_reason`, `quick_qc BOOL`, status adds `SKIPPED`;
  `period_run_voucher_links(id, org_id, period_run_id, voucher_id, step_id, linked_by, created_at, UNIQUE(period_run_id, voucher_id))`;
  `iso_ncr_capa_records`: add `created_at`, `verification_notes`, `source MANUAL|AUTO_QC`;
  `calibration_instruments`: add `location`, `range_spec`, `least_count`, `created_at`;
  `iso_checklist_items(id, org_id, clause, title, description, status NOT_STARTED|IN_PROGRESS|COMPLIANT|NOT_APPLICABLE, evidence_document_ids UUID[], notes, updated_by, updated_at)`.
- Documents: `doc_folders`: add `system_kind` (FY_ROOT|MONTH|BILLS|OPERATIONS|PAYROLL|MASTER_LIBRARY|MASTER_SOP|MASTER_DRAWINGS|MASTER_CALIBRATION|MASTER_TEMPLATES|RUN|CUSTOM), `UNIQUE NULLS NOT DISTINCT (org_id, parent_folder_id, name)`;
  `documents`: add `file_name`, `file_size`, `checksum_sha256`, `upload_status PENDING|READY`, `ocr_text`, `search_tsv tsvector GENERATED`, `previous_revision_id`, `template_id`, `review_comment`, `updated_at`, index GIN on search_tsv.
- Platform: `platform_global_config_versions(id, config_id, version, payload, effective_from DATE, change_reason, created_by, created_at)`,
  `platform_subscription_invoices(id, org_id, invoice_number, period_start, period_end, amount_inr, status DUE|PAID|VOID, paid_at, created_at)`,
  `platform_impersonation_sessions(id, admin_id, org_id, mode, ticket_reference, reason, expires_at, created_at, ended_at)`.
- All money/qty `NUMERIC(18,4)`; rates `NUMERIC(7,4)`; indexes on every FK + `(org_id, voucher_date)`, `(org_id, period_month)`.

### 3.8 Domain rules (skills: implementing-tally-accounting, implementing-iso-operations-docs)
- Voucher save: service validates `ΣDR == ΣCR` (Decimal), ≥2 entries for accounting types, ledgers belong to org & active, bill allocations sum ≤ entry amount, period not locked (`books_locked_until`), date inside an FY ≥ books_beginning_from. Number allocated from `voucher_types.next_number` with `SELECT … FOR UPDATE` (format `{prefix}{n:0{pad}}{suffix}`). Deferred trigger stays as backstop. Edits keep number; full before/after in audit. Cancel = status CANCELLED (excluded from all reports), never hard delete.
- Report math: only `status='REGULAR'` vouchers. Ledger balance = opening (signed by type) + ΣDR − ΣCR. Group natures from seeds (`07_ACCOUNTING_TAX_PAYROLL_RULES.md §1`).
- GST: tax split by `org.state_code` vs place of supply (party `state_code`, overridable per voucher; SEZ/export → IGST). Rates per line from stock item / ledger; slabs validated against `GST_SLABS` config effective on voucher date. Round-off to nearest rupee posted to `ROUND_OFF`.
- TDS: `TDS_SECTIONS` config (rates, thresholds, no-PAN 20%); computed via `/accounts/taxation/tds/compute`, posted as CR `TDS_PAYABLE` line by client-confirmed entries.
- Inventory valuation: WEIGHTED_AVG (perpetual moving average) and FIFO (layer consumption) as pure functions in `accounts/valuation.py` with unit tests; LIFO and STANDARD supported (STANDARD = opening_rate). Negative stock allowed but reported in exceptions.
- Payroll lock (one transaction): attendance finalized for all active employees → compute (`payroll/calc.py`, pure + tested: EPF 12% on min(basic+da, 15000) if applicable; employer EPS 8.33% capped 1250 + EPF 3.67% (+0.5% EDLI, +0.5% admin, from config); ESIC 0.75%/3.25% when gross ≤ 21000 (employee share rounded up to rupee); PT from state slab config; TDS 192 projection from IT slab config) → allocate SHOP_FLOOR_OPERATOR gross wages to runs by `run_allocations` share → `operations.interface.apply_payroll_allocation` → post PAYROLL voucher via accounts interface (DR DIRECT_WAGES per cost centre, DR ADMIN_SALARIES, DR EMPLOYER_PF_ESIC, CR SALARY_PAYABLE, CR EPF/ESIC/PT/SALARY_TDS payables) → generate payslip PDFs into `/FY/Month/Payroll & Statutory Challans` → status LOCKED_POSTED.
- Runs: create = snapshot published graph, create steps (one per node, `sequence` = topological order), cost centre (accounts interface), run folder (documents interface). First node(s) ACTIVE with `input_qty = planned_qty`.
  Execute step: `accepted + rejected + rework == input`; DIAMOND evaluates `pass_criteria` on measurements; Quick QC (`quick_qc=true` or measurements omitted for a field with nominal) fills each `qc_field` with its nominal value flagged `auto_filled=true`; rejected>0 → Stock Journal WIP→SCRAP (accounts interface) + NCR `OPEN` (`source=AUTO_QC`); accepted flows to PASS edge targets (their `input_qty += accepted`, status ACTIVE); rework flows to REWORK edge target if present else stays on the node as pending rework. Skip (reason required, node `skippable`) passes `input_qty` straight to PASS targets with status SKIPPED; Succeed = accept all input. TERMINATOR execute commits accepted units: Stock Journal WIP→FG. Run `complete` requires every reachable node PASSED/SKIPPED/LOCKED and posts the Manufacturing Journal (consumes BOM raw materials at valuation rate, CR direct costs, DR FG at unit cost, DR scrap at recovery value) and sets `computed_unit_cost`.
  Instrument guard: execute with `instrument_id` whose status is EXPIRED → 423 `INSTRUMENT_EXPIRED`. Signed-off/locked steps → 423 `STEP_LOCKED` unless FULL `operations.qc_signoff` + `override_reason` (audited OVERRIDE).
- Workflow versions: published versions are immutable; `new-version` copies to version+1 DRAFT; runs pin `workflow_version` + `graph_snapshot`.
- Documents: system-locked folders cannot be renamed/moved/deleted (409 `FOLDER_LOCKED`). Month tree auto-created by daily cron and lazily on first use. ISO approval: DRAFT→UNDER_REVIEW (editor WRITE) → review (iso_approval WRITE, reviewer ≠ preparer) → APPROVED (iso_approval FULL, approver ≠ preparer, requires reviewed_by) which atomically marks prior revisions of the same `iso_doc_number` OBSOLETE; UNDER_REVIEW→DRAFT = reject with comment. Approved/obsolete documents and documents linked to vouchers/steps cannot be deleted. Downloads only via signed URLs (≤5 min) issued after RBAC; storage keys `org/{org_id}/{yyyy}/{mm}/{uuid}/{sanitized_name}`; upload size ≤ 50 MB; MIME allowlist (pdf, png, jpeg, webp, heic, docx, xlsx, csv, txt).
- Template rendering: tokens `{{item.*}}`, `{{run.*}}`, `{{step.*}}`, `{{accounts.*}}`, `{{org.*}}`, `{{today}}` (full list from `GET /documents/template-tokens`); unknown tokens render empty and are reported in `warnings`. Rendering is pure string substitution on block text (no code execution).

### 3.9 Web architecture (both apps)
```
src/
  app/                      # routes only; thin pages that compose feature components
    (auth)/login, signup, verify, forgot, reset, mfa, auth/callback
    (personal)/me, me/security, me/organizations, organizations/new
    (tenant)/[orgSlug]/...  # accounts, operations, documents, organization  (user web)
  core/  api/client.ts (openapi-fetch + auth middleware: attach access token, X-Organization-ID, Idempotency-Key, refresh-once on 401 with single-flight)
         auth/ (AuthProvider: access token in memory only, bootstrap via /auth/refresh, logout)
         org/ (OrgProvider: active org from URL slug → id, /org/context permissions)
         permissions/Can.tsx (<Can permission="accounts.vouchers" level="WRITE">), usePermission()
         shortcuts/ (global key router: F4–F9, Alt+C, Alt+G, Esc, Ctrl+S, Ctrl+A accept)
         money.ts, dates.ts, query-keys.ts ([orgId, domain, ...])
  components/ui/            # shadcn primitives + InaiFlow design tokens
  components/shell/         # Sidebar, Topbar (org switcher, FY, search, create, notifications), AccBar, RBar
  features/<domain>/        # api hooks (useQuery/useMutation), components, schemas (zod) — files < 300 lines
  lib/api/schema.d.ts       # generated, do not edit
```
- Security in the browser: access token only in memory; no localStorage of tokens; CSP via `next.config` headers
  (`default-src 'self'; img-src 'self' blob: data: https://*.supabase.co; connect-src 'self' https://*.supabase.co; frame-ancestors 'none'`), `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy` (camera allowed self for scanner).
  All user-supplied HTML is rendered as text (report blocks are structured JSON → React elements; no `dangerouslySetInnerHTML`).
- Design system = the approved Claude Design canvas: Google Sans Flex/Inter, neutrals `#F9F9FB #F2F4F7 #EAECF0 #1D2939 #475467 #667085`, primary terracotta `#C35E49` (primary actions + active nav only), `#141414` (titles/key numbers only), accents teal `#0E9384`, indigo `#4F46E5`, sky `#0BA5EC`, violet `#7A5AF8`, orange `#EF6820`, status success `#12B76A` warning `#F79009` danger `#F04438`; small elements are rounded squares (radius 6–8px), compact KPI cards with light tinted icon tiles. Calm screens: one primary action per screen, "Get started" guides, Advanced sections collapsed. Accounts screens follow TallyPrime ergonomics (Gateway, right F-key bar, bill-style voucher entry, Enter-to-advance, Ctrl+A to accept).
- Logos: `client/*/web/public/brand/logo-light.png`, `logo-dark.png` (from project files).

### 3.10 Deployment & ops
- `server/vercel.json`: Python runtime, `api/index.py`, rewrites `/(.*)` → `/api/index`; cron `GET /api/v1/internal/cron/daily` at `30 20 * * *` (02:00 IST) with `Authorization: Bearer $CRON_SECRET`.
- DB from Vercel: Supabase transaction pooler (6543), SQLAlchemy `NullPool`, asyncpg `statement_cache_size=0`, `prepared_statement_cache_size=0`. Migrations run from CI/local with the session pooler (5432) `DATABASE_URL_MIGRATIONS`.
- Env (server): `APP_ENV`, `DATABASE_URL`, `DATABASE_URL_MIGRATIONS`, `JWT_SECRET`, `ADMIN_JWT_SECRET`, `MFA_ENCRYPTION_KEY`, `CRON_SECRET`, `CORS_ORIGINS` (only for local), `PUBLIC_USER_WEB_URL`, `PUBLIC_ADMIN_WEB_URL`, `STORAGE_PROVIDER=supabase|local`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `STORAGE_BUCKET=inaiflow-private`, `EMAIL_PROVIDER=console|resend`, `RESEND_API_KEY`, `EMAIL_FROM`, `TAX_GATEWAY=mock|sandbox`, `ADMIN_IP_ALLOWLIST`, `GOOGLE_CLIENT_ID/SECRET`.
  Startup refuses to run in `APP_ENV=production` with default/short secrets (≥32 bytes) or `STORAGE_PROVIDER=local`.
- Env (web): `SERVER_URL` (rewrite target), `NEXT_PUBLIC_APP_NAME`; admin web additionally `NEXT_PUBLIC_USER_WEB_URL` (impersonation launch).
- CI: `server` → ruff, import-linter, pytest (Postgres service); `client/*/web` → eslint, tsc, `next build`; contract job → regenerate openapi.json from `contract.api` and diff; server `test_contract.py` asserts every contract operation exists with the same method/path/required permission.

## 4. Feature scope of this build

Implemented end-to-end (server + UI): everything in specs 00–09 except the items in the deferred list. Deferred (adapters/interfaces + UI placeholders exist, real integration needs third-party credentials or heavy libraries):
1. Live IRP e-invoice / e-way bill (ships with `MockTaxGateway`; `SandboxIRP` adapter skeleton reads GSP creds).
2. OCR (ships client-side optional `tesseract.js` lazy load in scanner when available; server stores `ocr_text` sent by client).
3. XLSX bank statement import (CSV, OFX, MT940 implemented) and Tally XML **import** (export implemented).
4. Payment gateway for SaaS billing (manual invoices implemented).
5. GSTR-9 annual return (GSTR-1/3B/2B implemented).
6. Group consolidation & split-FY utilities.

## 5. Work breakdown & ownership (parallel agents)

| Stream | Owner dirs | Depends on |
|---|---|---|
| S0 Contract | `docs/api/*` | — (done first, by lead) |
| S1 Server foundation | `server/` scaffolding, `app/core`, `app/adapters`, `app/seeds`, `migrations/0001`, ALL `models.py`, modules identity/organization/rbac/platform, `tests/conftest.py`, `test_rls.py`, `test_contract.py` | S0 |
| S2 Accounts + Taxation | `app/modules/accounts`, `app/modules/taxation`, `migrations/0002_accounts.py` | S1 |
| S3 Payroll | `app/modules/payroll`, `migrations/0003_payroll.py` | S1 (uses accounts interface signatures; stubs allowed until S2 lands) |
| S4 Operations + Documents | `app/modules/operations`, `app/modules/documents`, `migrations/0004_ops_docs.py` | S1 |
| S5 Superadmin | `app/modules/superadmin`, `migrations/0005_superadmin.py` | S1 |
| W1 User web core | `client/user/web` scaffold, core/, shell, auth, personal, organization | S0 |
| W2 User web Accounts (+payroll, tax, reports) | `client/user/web/src/features/accounts`, `app/(tenant)/[orgSlug]/accounts` | W1 |
| W3 User web Operations + Documents | `features/operations`, `features/documents` + routes | W1 |
| W4 Admin web | `client/admin/web` | S0 |
| Lead | integration, type regeneration, security review, delivery | all |

Rules for agents: stay inside owned dirs; migrations 0002–0005 always exist (no-op if unused) with fixed `revision`/`down_revision` chain `0001_baseline ← 0002_accounts ← 0003_payroll ← 0004_ops_docs ← 0005_superadmin`; never edit another stream's files — if you need a change there, write it in `docs/plan/requests/<stream>.md`; each agent uses its own test database `inaiflow_test_<stream>`; TDD for domain logic (valuation, GST, payroll calc, step execution, permission resolution) — write the failing test first.

## 6. Verification gates (definition of done)
1. `uv run ruff check`, `uv run lint-imports`, `uv run pytest` green (RLS suite, contract conformance, domain unit tests, API integration tests per module).
2. Both webs: `pnpm lint`, `pnpm typecheck`, `pnpm build` green with types generated from the **server's** `/openapi.json`.
3. Contract conformance: 100 % of contract operations implemented with matching method/path/permission.
4. Security review checklist (`securing-multitenant-rbac`) passed by an independent reviewer agent; Semgrep (`p/python`, `p/nextjs`, `p/secrets`) clean of high findings.
5. Smoke E2E (Playwright, against local server): signup → verify → create org → create ledger → post sales voucher → trial balance balances → create workflow → publish → run → quick-QC step → NCR appears → upload document → approve.

## 7. Clarifications (binding, added during build)
1. **Uploads:** client `PUT`s the raw file bytes to `UploadTicket.upload_url` with every header in `UploadTicket.headers` (incl. `Content-Type`); no multipart. Then calls the matching confirm endpoint (`complete-upload`, or PATCH with `*_storage_key`). Local dev storage behaves identically.
2. **Idempotency-Key:** optional header on every tenant POST/PUT (declared in openapi). Web sends it for voucher create/update, step execute/skip/succeed, run postings, payroll lock, document upload-url.
3. **Impersonation launch:** `launch_url = {PUBLIC_USER_WEB_URL}/impersonate#token=<jwt>&org_id=<uuid>`; token never in query string; no refresh cookie, so reload ends the session (by design).
4. **enabled_modules keys:** `accounts, payroll, operations, documents, tally_xml_sync, irp_einvoice` (from plan's `enabled_modules`; missing key = false; no plan = all core modules true during trial).
5. **MFA at login:** `POST /auth/login` → `{status:"MFA_REQUIRED", mfa_token}`; `POST /auth/mfa/verify` accepts a 6-digit TOTP **or** a recovery code (format `xxxx-xxxx`, single use).
6. **Google OAuth failure:** callback redirects to `{PUBLIC_USER_WEB_URL}/login?error=oauth_failed` (or `oauth_disabled`); success redirects to `/auth/callback` after setting the refresh cookie.
7. **Expiry timestamps:** `access_expires_at` is an instant; web sends end-of-selected-day UTC.
