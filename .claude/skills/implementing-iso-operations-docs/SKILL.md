---
name: implementing-iso-operations-docs
description: Implements React Flow ISO 9001 process flowcharts, Period Execution Runs, QC diamond gate locking, NCR/CAPA triggers, and FY/Month locked document folders. Use whenever building operations workflows, period runs, run steps, calibration, dossier export, or the documents module (folders, templates, ISO approvals).
---

# ISO Operations & Document Control Rules

1. **Workflow Versioning:** Never mutate an active `workflow_templates` graph in place if `period_runs` reference it; increment `version` (`v1 -> v2`) so running batches keep their exact snapshot (`period_runs.workflow_version`).
2. **Diamond QC Gate Execution:** When a QC gate records `rejected_qty > 0`, atomically post a Stock Journal (via `accounts/interface.py`) moving rejected units from the WIP godown to the Scrap godown and create an `OPEN` record in `iso_ncr_capa_records`.
3. **Step Sign-Off Lock:** Once `signed_off_by` is recorded on a step, set `is_locked = True`. Reject subsequent edits unless caller holds `FULL` permission on `operations.qc_signoff` and supplies a non-empty `override_reason` (audit-logged as `OVERRIDE`).
4. **Calibration Guard:** Block QC step execution that references an instrument whose `calibration_instruments.status = 'EXPIRED'`.
5. **System-Locked Folders & ISO Revisions:** Block deletion/renaming of any `doc_folders` row where `is_system_locked = True`. When a document revision transitions to `APPROVED`, mark prior revisions of the same `iso_doc_number` as `OBSOLETE` in the same transaction.
6. **Run Creation Side Effects:** Creating a Period Run also creates its Cost Centre (Accounts) and its locked folder `/FY .../MM - Mon YYYY/Operations & Production Runs/<run_title>` (Documents) — through each module's `interface.py`.
7. **Frontend Canvas:** Load `@xyflow/react` with `next/dynamic` (no SSR); keep canvas state in a small `useFlowchartCanvasStore`.

## Reference
- Run/step and document state machines: `docs/specs/09_API_CONTRACTS_AND_STATE_MACHINES.md` sections 2A and 2B.
- Tables (`workflow_templates`, `period_runs`, `period_run_steps`, `iso_ncr_capa_records`, `calibration_instruments`, `doc_folders`, `documents`): `docs/specs/06_POSTGRES_DATABASE_SCHEMA.sql` sections 4 and 6.
