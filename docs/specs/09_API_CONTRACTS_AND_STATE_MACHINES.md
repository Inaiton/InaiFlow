# API CONTRACTS, RBAC MIDDLEWARE & STATE MACHINES

## 1. Request Authentication & Tenant Context Headers
Every tenant API request requires:
* `Authorization: Bearer <jwt_access_token>` (contains `user_id`, `email`, `mfa_verified`)
* `X-Organization-ID: <org_uuid>` (omitted only when operating in Personal Space `/me/*`)

### Backend Middleware Execution Order
1. **Verify JWT** -> Extract `user_id`.
2. **Validate Membership** -> Query `org_memberships` for `(org_id, user_id, status = 'ACTIVE')` and verify `access_expires_at IS NULL OR access_expires_at > NOW()`.
3. **Enforce Org Security Policy** -> If `org.security_settings.enforce_2fa_external == true` and user role is external collaborator, verify `mfa_verified == true`.
4. **Check RBAC Permission & Resource ACL** -> Verify required permission key (`NONE < READ < WRITE < FULL`) and check `resource_acl` overrides if accessing a specific `stock_item_id`, `period_run_id`, or `folder_id`.
5. **Set PostgreSQL RLS Context** -> Execute `SET LOCAL app.current_org_id = '<org_uuid>';` inside the DB transaction.

### Permission Keys (Sub-Module Matrix)
* `accounts.*`: `dashboard`, `vouchers`, `ledgers_groups`, `inventory_masters`, `banking`, `payroll_employees`, `payroll_runs`, `taxation`, `reports`
* `operations.*`: `dashboard`, `items`, `workflows`, `runs_execution`, `runs_accounting`, `qc_signoff`, `iso_compliance`
* `documents.*`: `explorer`, `capture_upload`, `editor`, `iso_approval`, `templates`
* `organization.*`: `profile`, `members`, `roles_rbac`, `security_policies`, `audit_logs`, `billing`
* Pre-seeded roles: `ORG_OWNER`, `ADMIN`, `ACCOUNTANT`, `QA_LEAD`, `OPERATOR`, `AUDITOR`.

---

## 2. Core State Machines

### A. Operations Period Run & Step Execution State Machine
* **Run States:** `PLANNED` -> `IN_PROGRESS` <-> `QC_HOLD` -> `COMPLETED` (or `CANCELLED`).
* **Diamond QC Gate Evaluation (`POST /api/v1/operations/runs/:runId/steps/:stepId/execute`):**
  1. Validate input measurements against node's `pass_criteria` expression.
  2. If `accepted_qty > 0`: advance accepted quantity to next downstream `PASS` node.
  3. If `rejected_qty > 0`:
     * Post automatic `Stock Journal` in **Accounts** moving `rejected_qty` from `WIP Godown` to `Scrap Godown`.
     * Auto-generate `iso_ncr_capa_records` entry (`status = 'OPEN'`) linked to `run_step_id`.
  4. When QA Lead calls `POST .../signoff`: set `is_locked = true`, record `signed_off_by` & timestamp. Subsequent edits require `FULL` permission on `operations.qc_signoff` + non-empty `override_reason`.

### B. ISO Document Approval State Machine (`/api/v1/documents/:docId/transition`)
* `DRAFT` -> `UNDER_REVIEW` -> `APPROVED` -> `OBSOLETE`.
* When `revision_no = 2` transitions to `APPROVED`, backend atomically updates `revision_no = 1` of the same `iso_doc_number` to `OBSOLETE` and logs both transitions in `org_audit_logs`.

### C. Monthly Payroll Lock & Auto-Voucher State Machine (`POST /api/v1/accounts/payroll/runs/:id/lock`)
Executed inside a single ACID database transaction:
1. Validate all active employees have attendance/LOP finalized.
2. Compute Earnings, Employee Deductions (`EPF`, `ESIC`, `PT`, `TDS`, `Loan EMI`), Employer Contributions, and Net Pay.
3. Sum `period_run_allocations` per `period_run_id` and update `period_runs.total_debit_cost` & `computed_unit_cost`.
4. Insert balanced `vouchers` + `voucher_entries` (`DR Direct Labor [tagged to Cost Centre]`, `DR Admin Salaries`, `DR Employer PF/ESIC`, `CR Salary Payable`, `CR Statutory Payables`).
5. Generate PDF payslips for each employee and save into `/Documents/FY.../Month/Payroll & Statutory Challans`.

---

## 3. Cross-Module Integration Matrix

| Trigger Event | Source Module | Automated Downstream Effect |
| :--- | :--- | :--- |
| **Create Organization** | **Organization** | Seeds 28 Tally Account Groups, GST ledgers, 6 RBAC roles, ISO templates, and locked `/FY 2026-27` folder tree in **Documents**. |
| **Instantiate Period Run** (`Component 1 - Sept 2026`) | **Operations** | Creates a matching **Cost Centre** in **Accounts** and auto-generates locked folder `/Documents/FY 2026-27/09 - Sept 2026/Operations/Component 1 - Sept 2026`. |
| **Accept / Reject Units in Workflow** | **Operations** | Updates WIP, Finished Goods, or Scrap stock quantities in **Accounts**; rejected QC gates auto-create an **NCR** in ISO Compliance. |
| **Post `Dr`/`Cr` or Assign Voucher in Run** | **Operations <-> Accounts** | Posts balanced double-entry vouchers in **Accounts** or links existing Purchase/Sales vouchers to workflow steps for `.docx`/`.pdf` dossier export. |
| **Lock Monthly Payroll Run** | **Accounts (Payroll)** | Allocates shop-floor wages directly into active **Operations** Period Runs, posts balanced Salary/PF/ESIC/TDS journals, and archives payslips/ECRs in **Documents**. |
| **Save Voucher with Scanned Bill** | **Accounts -> Documents** | Automatically files the scanned invoice PDF into `/Documents/FY.../Month/Bills & Vouchers` linked to the voucher number. |
| **Approve ISO Document Revision (`v2.0`)** | **Documents -> Operations** | Locks `v1.0` as `Obsolete` and updates active workflow steps to reference `v2.0` SOPs. |
