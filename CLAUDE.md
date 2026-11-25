# InaiFlow

Multi-tenant cloud ERP: Tally-grade accounting + payroll, ISO 9001 process control, FY/Month document vault, 4-tier RBAC.
Domain rules live in `.claude/skills/` and load only when relevant. Specs live in `docs/specs/` — read only the section you need.
The build plan is `docs/plan/IMPLEMENTATION_PLAN.md`; the API contract is `docs/api/contract.api` (generated `docs/api/openapi.json`).

## Layout (three major items)
```
client/
  user/web/          # Next.js tenant app (/accounts /operations /documents /organization, personal space)
    src/core/        # api client, auth session, X-Organization-ID, <Can> permission gate, shortcuts
    src/features/<domain>/
  admin/web/         # Next.js superadmin console
server/              # FastAPI modular monolith
  app/core/          # config, DB, JWT, RBAC/ACL guard, RLS context, audit, errors
  app/adapters/      # storage / email / pdf-docx export / tax-gateway providers
  app/seeds/         # default chart of accounts, roles, ISO templates, tax rules (pure data)
  app/modules/       # identity, organization, rbac, platform, accounts, taxation, payroll, operations, documents, superadmin
  migrations/        # Alembic (fixed chain 0001→0005)
docs/                # specs, plan, api contract, brand assets
```

## Stack
- Frontends: Next.js 16 App Router, React 19, TypeScript strict, Tailwind v4, shadcn/ui, TanStack Query/Table, zod + react-hook-form, openapi-fetch (types generated from `docs/api/openapi.json`), @xyflow/react.
- Server: Python 3.12, FastAPI, SQLAlchemy 2 async (asyncpg), Pydantic v2, Alembic, argon2, PyJWT, pyotp.
- DB/Storage: Supabase Postgres 17 (RLS via `inaiflow_app` role) + private Storage bucket. Server uses the transaction pooler (port 6543).
- Deploy: 3 Vercel projects (client/user/web, client/admin/web, server) + 1 Supabase project.

## Commands
```
pnpm install
pnpm dev                                   # both web apps
pnpm --filter @inaiflow/user-web dev | pnpm --filter @inaiflow/admin-web dev
pnpm lint && pnpm typecheck
python3 docs/api/gen_openapi.py            # regenerate openapi.json after editing contract.api
pnpm gen:api                               # regenerate web API types
cd server && uv sync && uv run uvicorn app.main:app --reload
cd server && uv run pytest
cd server && uv run alembic upgrade head
cd server && uv run python -m app.cli create-superadmin --email you@x.com --name "You"
```

## Non-negotiables
- Contract first: change `docs/api/contract.api` before any endpoint/payload change; server and both clients follow it.
- Money/qty: `Decimal` / `NUMERIC(18,4)`, JSON strings, never float.
- No cross-module model imports; use the other module's `interface.py`.
- Every tenant transaction runs `SET LOCAL ROLE inaiflow_app` + `app.current_org_id`.
- Schema changes only via Alembic.
- Tokens: access token in memory only; refresh token in HttpOnly cookie; web calls the API through same-origin `/api/v1` rewrite.
- Run long test suites, migrations and repo-wide scans in a subagent and report only the summary.
