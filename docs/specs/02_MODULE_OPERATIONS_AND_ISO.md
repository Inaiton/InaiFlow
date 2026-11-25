# MODULE 2: OPERATIONS (`/operations`)
## 1. Routes & Pages
* `/operations` — Dashboard (Active Period Runs, Rejection/Yield KPIs, Open NCR/CAPA, Calibration due alerts, ISO Audit Readiness score)
* `/operations/items` & `/:itemId` — Stock Items & Standalone Process Targets (2D/3D diagrams, tolerances, BOM links, custom typed fields, custom UoMs, historical Period Runs)
* `/operations/workflows` & `/editor/:id` — Visual Flowchart Studio (ISO template library + infinite Node Canvas with versioning v1 -> v2)
* `/operations/runs` & `/:runId` — Period Execution Objects (e.g., `Component 1 - Sept 2026`)
* `/operations/iso-compliance` — ISO 9001 Checklist, NCR/CAPA Tracker, Gauge Calibration Register, External Auditor Guest Access & 1-Click ISO Audit Dossier Export
## 2. Flowchart Shapes
* OVAL Start/Trigger (manual, monthly schedule, on GRN). RECTANGLE Process step (assigned role/operator, machine, cycle time, gauge check, custom QC fields). DIAMOND QC gate (evaluates entered values vs acceptance criteria; PASS advances; REJECT routes to Scrap / Rework loop / NCR). PARALLEL sub-process (concurrent checks). TERMINATOR End (commit finished units to FG inventory, close batch costing).
## 3. Run Workspace
* Step data entry & locking (input/accepted/rejected/rework + QC readings; QA sign-off locks gates).
* Step attachments & ad-hoc reports (auto-filed in /Documents).
* Direct Dr/Cr posting from run page (balanced voucher in Accounts); assign existing vouchers to steps. Money flow: Raw Materials + Direct Expenses + Allocated Payroll Labor - Scrap/Sales Credits = Net Run Cost & Unit Cost.
* Product decision (design phase): any step can be marked SKIPPED or SUCCESS on command (audited, reason required); "Quick QC": entering only totals auto-fills observed readings with nominal values.
## 4. Dossier Export (.docx & .pdf)
* P1 specs/diagram/custom fields/summary/sign-offs; P2 Dr/Cr money flow + unit cost; P3 executed flowchart + step log; P4+ step reports + appendix.
