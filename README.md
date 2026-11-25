# InaiFlow
Multi-tenant cloud ERP: Tally-grade accounting, GST/TDS and payroll, ISO 9001 process control, FY/month document vault, 4-tier RBAC.

| Part | Path | Stack |
|---|---|---|
| User web | `client/user/web` | Next.js 16, React 19, Tailwind 4, TanStack Query |
| Admin web | `client/admin/web` | Next.js 16 (superadmin console) |
| Server | `server` | FastAPI, SQLAlchemy 2 async, Postgres (RLS), Alembic |

Plan: `docs/plan/IMPLEMENTATION_PLAN.md` · API contract: `docs/api/contract.api` → `docs/api/openapi.json` · Design: `docs/design/`.

## Run locally
Needs Node 22 + pnpm 10, Python 3.12 + uv, Postgres 15+.
```
# one-time: a non-superuser owner role (RLS is only enforced for non-superusers)
psql -U postgres -c "CREATE ROLE inaiflow_owner LOGIN PASSWORD 'inaiflow_owner' CREATEDB;"
psql -U postgres -c "CREATE DATABASE inaiflow_dev OWNER inaiflow_owner;"

cd server && cp .env.example .env      # set MFA_ENCRYPTION_KEY: uv run python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())"
uv sync && uv run alembic upgrade head
uv run python -m app.cli create-superadmin --email you@example.com --name "You"
uv run uvicorn app.main:app --reload --port 8000

cd ../ && pnpm install
pnpm dev:user    # http://localhost:3000   (SERVER_URL defaults to http://localhost:8000)
pnpm dev:admin   # http://localhost:3001
```
Dev email is printed to the server log (verification and reset codes).

## Test
`cd server && uv run pytest` (creates `inaiflow_test_s1`; set `TEST_DATABASE_URL` to change) · `pnpm lint && pnpm typecheck && pnpm -r --filter ./client/*/web test && pnpm build`

## Deploy (Vercel + Supabase)
1. Supabase: create a project and a private bucket `inaiflow-private`. Run `uv run alembic upgrade head` against the **session** pooler (5432) with `DATABASE_URL_MIGRATIONS`.
2. Vercel project `server` (root `server/`): set `APP_ENV=production`, `DATABASE_URL` (transaction pooler 6543), `JWT_SECRET`, `ADMIN_JWT_SECRET`, `MFA_ENCRYPTION_KEY`, `CRON_SECRET`, `STORAGE_PROVIDER=supabase`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `EMAIL_PROVIDER=resend`, `RESEND_API_KEY`, `EMAIL_FROM`, `PUBLIC_USER_WEB_URL`, `PUBLIC_ADMIN_WEB_URL`. The app refuses to start in production with weak secrets, local storage or console email. The daily cron is in `server/vercel.json`.
3. Vercel projects for `client/user/web` and `client/admin/web`: set `SERVER_URL` to the server URL (admin also `NEXT_PUBLIC_USER_WEB_URL`).
