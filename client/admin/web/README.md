# @inaiflow/admin-web — Platform console

Separate Next.js 16 app for `platform_admins` (SUPERADMIN / SUPPORT_ADMIN / BILLING_ADMIN). Talks only to
`/api/v1/admin/*` (plus public `/api/v1/meta/permission-keys`) through a same-origin rewrite.

```
cp .env.example .env.local        # SERVER_URL, NEXT_PUBLIC_USER_WEB_URL
pnpm gen:api                      # openapi-typescript → src/lib/api/schema.d.ts + admin-roles.gen.ts
pnpm dev                          # http://localhost:3001
pnpm lint && pnpm typecheck && pnpm test && pnpm build
```

## Layout
- `src/app/` — thin routes: `(auth)/login`, `(console)/` dashboard, organizations, users, config, plans, billing, audit-logs, admins, system.
- `src/core/` — `auth/` (AuthProvider: access token in memory, bootstrap + single-flight refresh, 30-min idle logout),
  `permissions/` (`adminCan(role, action)` derived from the contract's `admin <ROLES>` lists via `scripts/gen-admin-roles.mjs`).
- `src/lib/` — `api/client.ts` (openapi-fetch, Bearer + `X-Requested-With`, refresh-once on 401), `money.ts` (BigInt ×10⁴, Indian grouping), `dates.ts`, `json-diff.ts`.
- `src/features/<area>/` — api hooks, components, schemas. Config editors live in `features/config/{editors,iso,doc}`.
- `src/components/ui` — own shadcn-style primitives; `components/shell` — dark sidebar (`#1D2939`), top bar with environment badge.

## Security
Access token never touches web storage (lint rule forbids `localStorage`/`sessionStorage`); refresh token is the HttpOnly
`if_art` cookie. Strict CSP, `frame-ancestors 'none'`, `X-Frame-Options: DENY`, `no-store` on pages, `noindex`.
No `dangerouslySetInnerHTML` (lint error). Every privileged/destructive action needs a typed reason.

Decisions: `docs/plan/decisions/W4.md`. Contract issues: `docs/plan/requests/contract.md`.
