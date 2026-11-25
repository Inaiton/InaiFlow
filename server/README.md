# InaiFlow server (FastAPI modular monolith)

## Run
```
cd server && uv sync
createdb -O inaiflow_owner inaiflow_dev          # a NON-superuser owner role (RLS must apply)
uv run alembic upgrade head                      # 0001_baseline ← 0002_accounts ← 0003_payroll ← 0004_ops_docs ← 0005_superadmin
uv run uvicorn app.main:app --reload             # http://localhost:8000/api/v1/health, /docs, /openapi.json
uv run python -m app.cli create-superadmin --email you@x.com --name "You"
uv run ruff check . && uv run ruff format --check . && uv run lint-imports && uv run pytest
```
Env vars: see `.env.example` (`app/core/config.py` is the source of truth). The app must connect as the
**same role that ran the migrations** (it owns the tables and is granted `inaiflow_app`).

## Tests — one database per stream
`TEST_DATABASE_URL=postgresql+asyncpg://inaiflow_owner:inaiflow_owner@localhost:5432/inaiflow_test_s2 uv run pytest app/modules/accounts`
(default `inaiflow_test_s1`). The DB is dropped/created and migrated once per session (`TEST_DB_REUSE=1` keeps it).
No truncation: factories create unique users/orgs. Fixtures (`tests/plugin.py`): `client` (httpx ASGI, unique IP),
`owner` (verified user + org created through the real `POST /organizations`, i.e. fully seeded), `outbox`.
Factories (`tests/factories.py`): `create_user(mfa=...)`, `add_member(org_id, "ACCOUNTANT", mfa=, access_expires_at=)`,
`org_with_owner(client)`, `role_id`, `set_org`, `sql("...", **params)`. `actor.headers` carries Bearer + `X-Organization-ID`.
Put module tests in `app/modules/<x>/tests/`.

## Writing a module (reference: `app/modules/organization`)
```
router.py      thin handlers (≤ ~15 lines): parse DTO, inject ctx/db, call ONE service fn, return schema
schemas.py     Pydantic models named exactly like the contract models; money = app.core.money.DecimalStr
service.py     business rules, raise app.core.errors.*Error (never HTTPException), write audit rows
repository.py  queries only; flush, never commit
models.py      (already written by S1 — must match the migration; drift test enforces it)
interface.py   the only thing other modules may import (import-linter enforces it)
```
Register routers: append to `ROUTERS` in `app/main.py`, or just export `router` (or `routers = [...]`) from
`app/modules/<x>/router.py` — `create_app()` auto-includes accounts/taxation/payroll/operations/documents/superadmin.

### Tenant route
```python
Ctx = Annotated[TenantContext, Depends(require("accounts.vouchers", "WRITE"))]


@router.post("/accounts/vouchers", response_model=VoucherOut, status_code=201)
async def create(body: VoucherIn, ctx: Ctx, db: TenantDB, idem: Idem) -> VoucherOut:
    return await idem.save(await service.create_voucher(db, ctx, body), 201)
```
* `require(key, level)` runs the full plan §3.4 pipeline (session, membership, expiry, org status, 2FA policy,
  impersonation, permission). `require(None)` = any member. `acl_resource="PERIOD_RUN"` also admits users whose
  module level is too low but who hold an ACL grant on that resource type — then filter in the service.
* `TenantDB` = ONE transaction already running `SET LOCAL ROLE inaiflow_app` + `app.current_org_id/user_id`.
  It commits when the handler returns and **before** the response is sent: commit-time failures (deferred
  double-entry trigger → 400 `DOUBLE_ENTRY_IMBALANCE`, unique violations → 409) become error responses.
  Services must not call `commit()`/`begin()`; use `db.flush()` / `db.begin_nested()`.
* Personal/platform routes: `CurrentUser` + `DB` (no RLS role; filter explicitly). Admin: `require_admin("SUPERADMIN", ...)`
  (or `require_admin()` = ANY) → `AdminPrincipal`; public admin auth routes call `check_admin_ip(request)`. Cron: `require_cron()`.
* Errors: `raise NotFoundError()` (also for cross-tenant ids), `PeriodLockedError`, `StepLockedError` … one class per contract `ErrorCode`.

### ACL (record level)
`await assert_resource_access(ctx, db, "PERIOD_RUN", run_id, "operations.runs_execution", "WRITE")` (NONE → 404, too low → 403);
lists: `f = await acl_list_filter(ctx, db, "STOCK_ITEM", "operations.items"); stmt.where(f.clause(StockItem.id))`;
`filter_accessible(...)`, `rbac.interface.resource_levels(...)`. USER row beats ROLE row; override replaces the module level; owner = FULL.

### Audit, sequences, idempotency, money, FY
* `await write_audit(db, ctx, "ACCOUNTS", "UPDATE", "voucher", v.id, before=old, after=new, reason=..., changed_only=True)`
  (Decimal→str; actor_type USER/SYSTEM/PLATFORM_ADMIN handled from ctx) or `@audited(module=, action=, entity=)`.
* `n = await next_value(db, ctx.org_id, "NCR"); format_number("NCR-", n, 4)` — gap-free per org (row-locked upsert).
* `Idem` dependency + `await idem.save(out, status)`; replay sets `Idempotent-Replayed: true`; other body → 409.
* `app.core.money`: `D`, `q2`, `q4`, `round_rupee`, `ceil_rupee`, `pct`, `to_str`, `DecimalStr` (rejects floats).
* `app.core.fy`: `fy_for_date(d, org.fy_begins_from)` → `FY 2026-27`; `month_folder_name(d)` → `"09 - September 2026"`
  (single format: `"{MM} - {Full month} {YYYY}"`); `parse_month("2026-09")`.
* Configs: `platform.interface.get_config(db, "PAYROLL_STATUTORY", "EPF", on_date=d)` (effective-dated). Keys:
  ACCOUNT_GROUPS/default, DEFAULT_LEDGERS/default, VOUCHER_TYPES/default, GST_SLABS/default, TDS_SECTIONS/default,
  PAYROLL_STATUTORY/{EPF,ESIC,PT_SLABS,INCOME_TAX}, ISO_WORKFLOW_TEMPLATES/<key>, DOC_REPORT_TEMPLATES/<key>,
  FOLDER_TEMPLATES/{MONTHLY,MASTER_LIBRARY}, DEFAULT_ROLES/<role>, ISO_CHECKLIST/ISO_9001_2015, UOM, INDIAN_STATES, FEATURE_FLAGS.

### Adapters
* Storage: `get_storage().create_upload_ticket(key, ct, size)` / `create_download_url(key, filename=)` / `head` / `put_bytes` /
  `get_bytes` / `delete`; keys via `build_org_key(org_id, name)`; `validate_upload(ct, size)` (50 MB, MIME allowlist).
  Clients PUT raw bytes to `upload_url` with `headers` (local dev: `/api/v1/storage/local/{token}`, 404 unless local).
* Email: `await get_email().send(EmailMessage(to, subject, text, tag=...))` (console provider keeps `.outbox`).
* Export: `get_exporter().render(Report(title, blocks, Letterhead(...), watermark=), "pdf"|"docx")` — block types in `app/adapters/export.py`.
* Tax gateway: `get_tax_gateway().generate_irn(payload)` / `cancel_irn` / `generate_eway_bill` (Mock is deterministic).

### Migrations
Only in your fixed slot (`migrations/versions/0002_accounts.py` S2, `0003_payroll.py` S3, `0004_ops_docs.py` S4,
`0005_superadmin.py` S5). Keep `revision`/`down_revision`. New tenant tables need `org_id`, ENABLE+FORCE RLS, a
`tenant_isolation_<t>` policy (`NULLIF(current_setting('app.current_org_id', true), '')::uuid`), an
`owner_access_<t>` policy `TO current_user`, and grants to `inaiflow_app` — copy the pattern in
`migrations/baseline_security.py`. Model changes go in the same commit (`tests/test_schema_drift.py`).
`models.py` files are S1's; if you need a column, add it in your migration **and** the model.

### Interface stubs you must fill (signatures are binding)
* S2 `accounts.interface`: `post_system_voucher`, `create_cost_centre`, `get_stock_item`, `list_vouchers_for_run`, `link_voucher_to_run`
  (already real: `seed_org_accounts`, `get_ledger_ids_by_code`, `get_system_godown_ids`, `resource_names`).
* S4 `documents.interface`: `create_run_folder`, `store_generated_file`, `get_document` (real: `ensure_month_folders`/`MonthFolders`,
  `seed_org_documents`, `resource_names`, `storage_used_bytes`); `operations.interface`: `get_runs_by_ids`,
  `apply_payroll_allocation`, `list_step_executions_by_month` (real: `seed_org_operations`, `resource_names`, `refresh_calibration_statuses`).
* S3 `payroll.interface` (real: `seed_org_payroll`). S5 `superadmin.interface` (real: `write_platform_audit`, `get_config`);
  impersonation tokens: `app.core.security.create_impersonation_token(...)`; admin tokens: `create_admin_access_token`, `create_mfa_token(admin=True)`.
* Also available: `organization.interface` (`get_org_brief`, `update_accounts_settings`, `invite_member`, `is_member`),
  `identity.interface` (`user_briefs`, `user_brief_by_email`, `check_password`), `rbac.interface` (`get_role`, `roles_by_ids`, `resource_levels`).

## Deploy (Vercel)
`vercel.json` rewrites everything to `api/index.py` and schedules `GET /api/v1/internal/cron/daily` at 20:30 UTC
(Vercel sends `Authorization: Bearer $CRON_SECRET`). On Vercel the engine uses NullPool automatically.
