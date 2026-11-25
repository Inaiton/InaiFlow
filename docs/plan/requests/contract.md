
## From W4 (admin web)
1. **BUG — `TokenOut` is defined twice** (`auth (user)` line ~50 as `{access_token, token_type, expires_in}` and `documents` line ~517 as
   `{token, label, group, sample}`). The generator keeps the last one, so `LoginSuccessOut.token` / `AdminLoginSuccessOut.token` are typed as the template
   token. Please rename the documents model (e.g. `TemplateTokenOut`) and regenerate. Admin web guards the shape at runtime meanwhile.
2. Add `reason: str` to `InvoiceStatusIn`, `SubscriptionInvoiceIn`, `AdminAccountUpdateIn`, `PlanIn`/`PlanUpdateIn` so the typed confirmation reason lands in `platform_audit_logs`.
3. Enumerate string fields used as enums: `LifecycleIn.action` (ACTIVATE|SUSPEND|ARCHIVE|EXTEND_TRIAL), `ImpersonateIn.mode` (READ_ONLY|FULL_SUPPORT),
   `UserActionIn.action` (SUSPEND|UNSUSPEND|RESET_MFA|VERIFY_EMAIL|REVOKE_SESSIONS), `InvoiceStatusIn.status` (PAID|VOID), org status filter values. Admin web sends exactly these.
4. Add `GET /admin/meta/template-tokens` (admin ANY) returning the template token catalogue for the report template editor (tenant endpoint needs org context).
5. Type `AdminDashboardOut.signups_series` (e.g. `SignupPoint { date: date  count: int }[]`); admin web currently accepts `{date|month|period, count|value}`.
6. Optional: `GET /admin/organizations/{org_id}/members` (SUPERADMIN) for the transfer-owner picker; admin web currently searches `/admin/users` and checks `memberships`.

### Resolved by lead (2026-11-24)
All six W4 items applied to contract.api and regenerated: `TemplateTokenOut` rename, `reason` on plan/invoice/admin-update bodies,
enums LifecycleAction / ImpersonationMode / UserAction / InvoiceStatus / OrgStatus, typed `SignupPoint`, `GET /admin/meta/template-tokens`,
`GET /admin/organizations/{org_id}/members`. Generator now rejects duplicate model/enum names.

## From W1 (user web core)
1. **Idempotency-Key not declared.** Plan §3.1 makes it required for voucher create / step execute, but no operation declares the optional
   `Idempotency-Key` header, so it can't be typed. Please add it as an optional header param on mutating tenant operations. (User web sends it via
   `idempotencyHeader()` meanwhile.)
2. **Impersonation launch format.** `ImpersonateOut.launch_url` should be specified as `${PUBLIC_USER_WEB_URL}/impersonate#token=<jwt>&org_id=<uuid>`
   (fragment, never query). User web parses `token` + `org_id` (falls back to JWT claim `org_id` / `imp.org_id`) and never calls `/me` or `/auth/refresh` with it.
3. **UploadTicket semantics.** `PUT /storage/local/{token}` is `multipart` while Supabase signed URLs take raw bytes. Please fix one rule, e.g. "if
   `headers` contains `Content-Type`, PUT the raw file; otherwise multipart field `file`" (this is what user web implements), or make local storage raw too.
4. **`enabled_modules` keys** are free-form. Please enumerate (proposal: `accounts | payroll | operations | documents`). Missing key = enabled in the web.
5. **String fields that are really enums** (web currently hard-codes values): `MemberOut.status` / `MemberUpdateIn.status` (ACTIVE|SUSPENDED),
   `InvitationOut.status` (PENDING|ACCEPTED|DECLINED|EXPIRED|REVOKED), `JoinRequestOut.status` / `MyJoinRequestOut.status`, `MyOrgOut.membership_status`,
   `OrgCreateIn.gst_reg_type` (REGULAR|COMPOSITION|UNREGISTERED|SEZ), `OrgCreateIn.industry_type`, `AclIn.subject_type` (ROLE|USER),
   `AclIn.resource_type` / `AclGrantIn.resource_type` (STOCK_ITEM|PERIOD_RUN|DOC_FOLDER|GODOWN), `AuditLogOut.module|action|actor_type`, `ImpersonationInfo.mode`.
6. **MFA login signalling**: login returns `200 LoginOut{status: MFA_REQUIRED, mfa_token}`; the `MFA_REQUIRED` error code is also used by the tenant
   pipeline (403). Please confirm login never returns 403 MFA_REQUIRED (web handles both). Also confirm `MfaVerifyIn.code` accepts a recovery code.
7. **OAuth failure**: specify how `/auth/oauth/google/callback` reports failure on `redirect_to` (web reads `?error=<code>`, e.g. `access_denied`).
8. Optional: `TransferOwnershipIn.code` (TOTP) — the design asks for an authenticator code; contract has password only.
9. Optional: `MyOrgOut.gstin` + `city` for the org switcher subtitle (design: "ORG-8492 · GSTIN … · Coimbatore, TN").

## From S1 (server foundation) — values the server actually emits (please enumerate in the contract)
1. `InvitationOut.status`: `PENDING | ACCEPTED | REJECTED | EXPIRED | CANCELLED` (decline = REJECTED, org cancels = CANCELLED; not DECLINED/REVOKED as guessed in W1 #5).
2. `MyJoinRequestOut.status` / `JoinRequestOut.status`: `PENDING | ACCEPTED | REJECTED | CANCELLED`.
3. `MemberOut.status`, `MyOrgOut.membership_status`: `ACTIVE | SUSPENDED | EXPIRED` (REVOKED members are hidden unless `?status=REVOKED`);
   `MemberUpdateIn.status`: `ACTIVE | SUSPENDED`.
4. `AuditLogOut.actor_type`: `USER | SYSTEM | PLATFORM_ADMIN`; `role_code` may be `SYSTEM` / `SUPPORT_IMPERSONATION`.
5. W1 #6 confirmed: login never returns 403 MFA_REQUIRED (200 + `status=MFA_REQUIRED`); `MfaVerifyIn.code` accepts TOTP or a `xxxx-xxxx` recovery code.
6. W1 #8/#9 not implemented (contract unchanged): transfer-ownership re-checks password only; MyOrgOut has no gstin/city.

## From W3 (user web operations + documents)
1. Enumerate string enums the web hard-codes: `NcrOut.status` (OPEN|INVESTIGATING|VERIFIED_CLOSED), `ChecklistItemOut.status` (web assumes NOT_STARTED|IN_PROGRESS|COMPLIANT|NOT_APPLICABLE),
   `InstrumentOut.status`, `WorkflowSummary.status` (DRAFT|PUBLISHED|ARCHIVED), `NodeConfig.trigger` (MANUAL|SCHEDULED_PERIOD_START|ON_GRN), `reject_action` (SCRAP_NCR|SCRAP|REWORK|NCR),
   `PassCriteria.mode` (ALL_IN_TOLERANCE|MANUAL|EXPRESSION), `QcField.type` (NUMBER|TEXT|BOOL), `source_type`, `template_type`, `MoneyFlowLine.source`.
2. Specify rendered `qc_table` block data after `POST /documents` with a step context. Web reads `rows: [{parameter, spec, observed, auto|auto_filled, result}]` (or `[[...]]`) and pre-fills empty tables itself from the step.
3. `TemplateTokenOut.token`: with or without `{{ }}`? Web accepts both.
4. Which money-flow lines may be unlinked (`DELETE …/linked-vouchers/{id}`)? Web offers unlink on any line with a `voucher_id` and shows the server error otherwise.

## From W2 (user web accounts)
1. Enumerate string enums used by the accounts UI (currently matched to server code): `ReconciliationOut` `show`, `EinvoiceOut.kind`, statutory `{kind}`, trial-balance `mode`, ageing `kind`, `PayrollSettings.working_days_basis`, `InventoryIn.movement_type`, `GodownOut.godown_type`, `EmployeeOut.employee_category`, `PayrollRunOut.status`, `StatementLineOut.status`.
2. Type the `json[]` payloads of `Gstr1Out` (b2b…hsn), `Gstr3bOut` sections and `TdsChallanOut.by_section` so the web can render named columns.
3. Optional: `EntryOut.role` (PARTY | ITEM_LEDGER | TAX | ROUND_OFF | TDS) so invoice edit can rebuild the invoice exactly; `GET /documents/folders/for-date?date=&system_kind=BILLS` to avoid a 3-call folder walk when attaching bills.
