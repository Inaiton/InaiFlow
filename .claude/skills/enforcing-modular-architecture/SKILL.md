---
name: enforcing-modular-architecture
description: Enforces modular monolith boundaries, vertical domain slicing, and cross-module interface contracts when creating, modifying, or refactoring features in server, client/user/web, or client/admin/web. Use whenever adding a new module, endpoint, feature folder, adapter, or moving code between modules.
---

# Modular Architecture Rules

1. **Vertical Slicing Only:** Every backend module in `server/app/modules/<domain>/` must self-contain `router.py`, `schemas.py`, `service.py`, `repository.py`, `models.py`, and `interface.py` (plus `events.py` when it emits domain events, and its own `tests/`).
2. **Strict Layer Flow:** `Router -> Service -> Repository -> DB`. Repositories never import Services; Services never import FastAPI `Request` or raise `HTTPException` (raise domain exceptions such as `DoubleEntryImbalanceError`, `StepLockedError`, `InsufficientPermissionError`; global handlers map them to 400/403/409).
3. **Thin Routers, Fat Services:** Route handlers stay under ~15 lines: parse the Pydantic DTO, inject `current_user` / `org_context` / `db_session`, call one service method, return the response schema.
4. **Transactions at the Service Layer:** Never commit inside a repository. Open `async with db.begin():` in the service so multi-step operations succeed or roll back together.
5. **Zero Cross-Module DB Queries:** Never query another module's SQLAlchemy models directly. Call its public `interface.py` (e.g., `accounts_interface.post_system_voucher()`). Enforce with `import-linter` (Python) and `eslint-plugin-boundaries` (TS).
6. **Adapter Pattern:** Wrap external I/O (Supabase Storage, Cloudinary, PDF/DOCX builders, GST/IRP gateways) behind abstract classes in `server/app/adapters/` (`StorageProvider`, `DocumentExportProvider`, `TaxGatewayProvider`).
7. **Typed Contracts:** Pydantic v2 on the server; frontends consume auto-generated types/hooks from `each web app's generated `src/lib/api/schema.d.ts`` (from `/openapi.json`). Never hand-write API payload shapes.
8. **Frontend Isolation:** In `client/user/web` and `client/admin/web`, keep all API calls, TanStack Query keys (`[orgId, domain, ...]`), and domain components inside `src/features/<domain>/`. Keep files under 300 lines; split large screens into `features/<domain>/components/`. Never write `if (user.role === 'ADMIN')` in components — use `<Can level="..." permission="...">`.
9. **Migrations Only:** All schema changes go through versioned Alembic migrations.

## Reference
- Monorepo layout and module list: `CLAUDE.md`.
- Cross-module effects (what each action triggers in other modules): `docs/specs/09_API_CONTRACTS_AND_STATE_MACHINES.md`. Read only the section you need.
