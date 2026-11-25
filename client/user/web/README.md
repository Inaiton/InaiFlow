# @inaiflow/user-web

Tenant web app for InaiFlow: auth, personal space, organization admin, and the shell that the Accounts (W2) and
Operations/Documents (W3) features plug into. Next.js 16 App Router · React 19 · TS strict · Tailwind v4 · Radix (shadcn-style kit) ·
TanStack Query/Table · zod 4 + react-hook-form · openapi-fetch.

## Scripts

| Script | What it does |
|---|---|
| `pnpm dev` | Dev server on :3000 (`/api/v1/*` is rewritten to `SERVER_URL`) |
| `pnpm build` / `pnpm start` | Production build / serve |
| `pnpm lint` | ESLint flat config (next core-web-vitals + typescript, bans `any`, web storage, `dangerouslySetInnerHTML`) |
| `pnpm typecheck` | `tsc --noEmit` |
| `pnpm gen:api` | Regenerate `src/lib/api/schema.d.ts` from `docs/api/openapi.json` — **never edit it, never hand-write payload types** |
| `pnpm test` | Vitest for pure utils (money, dates, permissions, shortcut parser, error mapping, json diff, schemas) |

Run `pnpm install` from the repo root (workspace lockfile lives there).

## Env

| Var | Default | Purpose |
|---|---|---|
| `SERVER_URL` | `http://localhost:8000` | Rewrite target for same-origin `/api/v1/*` (keeps the refresh cookie first-party); also added to CSP `connect-src`/`img-src` |
| `NEXT_PUBLIC_APP_NAME` | `InaiFlow` | Title |

## Structure

```
src/
  app/                         routes only (thin pages)
    (auth)/  login signup verify forgot reset auth/callback impersonate
    (personal)/  me  me/security  me/organizations  organizations/new        ← RequireAuth + PersonalShell
    (tenant)/o/[orgSlug]/  page (home) · organization/* · accounts|operations|documents (W2/W3)  ← TenantGate + AppShell
  core/
    api/client.ts              `api` (personal), `createOrgClient(orgId)`, `unwrap`, `refreshSession`, `idempotencyHeader`
    api/types.ts               `Schemas["X"]`, `OrgPaths`
    api/errors.ts, error-messages.ts   ApiError {status, code, message, details, fieldErrors}, describeError(), errorMessage(code)
    auth/                      AuthProvider/useAuth, session-store (memory only), RequireAuth, safeNext
    org/OrgProvider.tsx        useOrg() → { orgId, slug, context (/org/context), api, refetchContext }
    permissions/               <Can>, useCan, usePermission, hasLevel/resolveLevel
    shortcuts/                 useShortcut, useShortcutScope, parser
    money.ts dates.ts query-keys.ts forms.ts upload.ts prefs.ts
  components/ui/               design-system kit (import from "@/components/ui")
  components/shell/            Sidebar, Topbar, OrgSwitcher, CommandPalette (Alt+G), CreateMenu (Alt+C), HelpOverlay (?), ImpersonationBanner, nav-config
  features/<domain>/           api.ts (hooks) · components/ · schemas — files < 300 lines
  lib/api/schema.d.ts          generated
```

W2 owns `src/features/accounts/**` + `src/app/(tenant)/o/[orgSlug]/accounts/**`; W3 owns `features/{operations,documents}` + those route folders.
Replace the placeholder `page.tsx` in your route folder. You may edit your module's entries in `components/shell/nav-config.ts` and
`components/shell/create-items.ts` (hrefs are relative to `/o/<slug>`); don't change shell/core behaviour — request it in `docs/plan/requests/W1.md`.

Planned hrefs already wired in nav / Alt+C / palette (create these routes):
`/accounts` (Gateway), `/accounts/dashboard`, `/accounts/vouchers`, `/accounts/vouchers/new?type=SALES|PURCHASE|PAYMENT|RECEIPT|JOURNAL|CONTRA`,
`/accounts/daybook`, `/accounts/masters`, `/accounts/masters/ledgers/new`, `/accounts/inventory`, `/accounts/inventory/items/new`, `/accounts/banking`,
`/accounts/payroll`, `/accounts/payroll/employees/new`, `/accounts/taxation`, `/accounts/reports`, `/accounts/utilities`;
`/operations`, `/operations/items`, `/operations/workflows`, `/operations/workflows/new`, `/operations/runs`, `/operations/runs/new`, `/operations/iso-compliance`;
`/documents` (`?upload=1` opens upload), `/documents/editor`, `/documents/scan`, `/documents/templates`.

## How to add a feature (W2/W3)

### 1. API hooks — `features/<domain>/api.ts`

```ts
"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { idempotencyHeader, unwrap } from "@/core/api/client";
import type { Schemas } from "@/core/api/types";
import { useOrg } from "@/core/org/OrgProvider";
import { qk } from "@/core/query-keys";

export function useLedgers(query: { q?: string; limit: number; offset: number }) {
  const { orgId, api } = useOrg();                       // org-bound client: X-Organization-ID injected
  return useQuery({
    queryKey: qk.org(orgId, "accounts", "ledgers", query), // ALWAYS [orgId, domain, ...]
    queryFn: () => unwrap(api.GET("/api/v1/accounts/ledgers", { params: { query } })),
    placeholderData: (prev) => prev,                     // smooth server pagination
  });
}

export function useCreateVoucher() {
  const { orgId, api } = useOrg();
  const qc = useQueryClient();
  return useMutation({
    // generate the key once per user submission (e.g. useState(() => crypto.randomUUID())) and reuse it on retry
    mutationFn: ({ body, key }: { body: Schemas["VoucherIn"]; key: string }) =>
      unwrap(api.POST("/api/v1/accounts/vouchers", { body, headers: idempotencyHeader(key) })),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.org(orgId, "accounts") }),
    meta: { successMessage: "Voucher saved" },           // success toast; errors toast globally
  });
}
```

- Types: `Schemas["LedgerOut"]` etc. Paths are the full `/api/v1/...` contract paths.
- Errors: `unwrap` throws `ApiError` (`code` from contract `ErrorCode`, `fieldErrors` from details). Mutations toast `describeError(err)` automatically —
  set `meta: { silentError: true }` when you render the error yourself. Queries: show `<ErrorState message={describeError(q.error)} onRetry=…/>` inline.
- 401 handling (single-flight refresh + retry, logout to `/login?next=`) is automatic. 4xx are never retried.
- Money/qty are **strings**. Use `core/money.ts` (`add`, `sub`, `mul`, `sum`, `cmp`, `isZero`, `round`, `formatMoney("1234567") → ₹12,34,567.00`,
  `formatQty`, `parseMoneyInput`). Never `Number()` a decimal for math.
- Dates: `core/dates.ts` (`fyForDate`, `monthsOfFy`, `monthKey → "YYYY-MM"`, `monthLabel → "Sept 2026"`, `formatDate`, `todayIso`). FY comes from `useOrg().context.current_fy`.
- Uploads: get an `UploadTicket` from the API, then `uploadToTicket(ticket, file)`; validate first with `validateFile`.

### 2. Permission gating — never check role codes

```tsx
<Can permission="accounts.vouchers" level="WRITE"><Button variant="primary">New voucher</Button></Can>
const canCancel = useCan("accounts.vouchers", "FULL");
```
Levels: `NONE < READ < WRITE < FULL`; owner is always FULL. Nav items hide automatically from `nav-config.ts` `perms` (≥ READ on any).

### 3. Forms — zod + react-hook-form

```tsx
const schema = z.object({ name: z.string().trim().min(1), amount: z.string().refine(isDecimal) });
const form = useZodForm(schema, { defaultValues: { name: "", amount: "" } });
const onSubmit = form.handleSubmit(async (v) => { try { await save.mutateAsync(v); } catch (e) { applyServerErrors(form, e); } });

<Field label="Amount" error={form.formState.errors.amount?.message} required>
  <Controller control={form.control} name="amount" render={({ field }) =>
    <DecimalInput value={field.value} onValueChange={(v) => field.onChange(v ?? "")} prefix="₹" />} />
</Field>
```
`Field` wires `id`/`aria-invalid`/`aria-describedby` into its single child. Use `FieldRow` for 2-column rows, `AdvancedSection` for collapsed extras.

### 4. Page layout & UI kit (`@/components/ui`)

- Every page: `<PageHeader crumbs title description actions />` — **one primary action** (`variant="primary"`, terracotta).
- `Card` (title/description/actions), `KpiCard` + `KpiGrid`, `Badge`/`StatusBadge` (tinted chips; `statusTone()`), `IconTile`, `Avatar`,
  `EmptyState`, `ErrorState`, `Hint` (callout), `Skeleton`, `Spinner`, `Meter`, `GetStartedGuide`, `Stepper`, `Section`, `AdvancedSection`,
  `Tabs/TabsList/TabsTrigger/TabsContent`, `Segmented`, `Dialog/DialogContent` (title, description, footer), `Sheet/SheetContent` (drawer),
  `ConfirmDialog` (optional `requireReason`, `confirmText`), `DropdownMenu*`, `Popover`, `Tooltip`, `Select` (Radix), `NativeSelect`, `Combobox`
  (cmdk; `onSearch` for server search), `Input` (`prefix`/`suffix`), `Textarea`, `DecimalInput`, `DatePicker` (`mode="month"` for `YYYY-MM`),
  `Switch`/`SwitchRow`, `Checkbox`/`CheckboxRow`, `Kbd`/`KbdCombo`, `JsonDiff`/`JsonBlock`.
- `DataTable`: `columns: ColumnDef<T, unknown>[]`, `data`, `loading`, `empty`, `onRowClick`, `getRowId`, `meta: { align: "right" }` for numbers,
  `pagination={{ total, limit, offset, onOffsetChange }}` for contract `Page<T>` (omit for client pagination).
- Tokens (Tailwind): `bg-canvas|surface|subtle`, `border-line`, `text-ink|fg|fg-3|fg-muted`, `bg-primary`, tones `*-tint`/`*-text` for
  success|warning|danger|indigo|sky|violet|teal|orange. Radius 6–8 px for small elements. No raw HTML injection (`dangerouslySetInnerHTML` is lint-banned).

### 5. Keyboard shortcuts

```tsx
useShortcutScope("voucher");                                         // while the voucher screen is mounted
useShortcut("f8", () => switchType("SALES"), { scope: "voucher", description: "Sales" });
useShortcut("ctrl+a", accept, { scope: "voucher", description: "Save voucher" });
useShortcut("escape", close, { scope: "voucher" });
```
The highest active scope wins over `global`; plain keys don't fire while typing, modifiers/F-keys/Esc do (`allowInInputs` to override).
Shortcuts with a `description` appear in the `?` help overlay. Global: Alt+G palette, Alt+C create, `?` help.
Add palette entries from a feature with `useRegisterCommands("accounts", items)` (memoise `items`).

### 6. Toasts

`import { toast } from "sonner"` for ad-hoc messages; prefer `meta.successMessage` on mutations.

## Security notes
- Access token lives only in `core/auth/session-store.ts` memory; refresh token is the HttpOnly `if_rt` cookie (Path `/api/v1/auth`).
- `?next=` redirects go through `safeNext()` (relative only).
- Security headers/CSP in `next.config.ts` (nonce-free; `camera=(self)` for the scanner).
- Impersonation: `/impersonate#token=…&org_id=…` — token in memory only, fragment cleared, yellow banner, no personal space.
