# MODULE 3: DOCUMENTS (`/documents`)
## 1. System-Locked Folder Hierarchy (is_system_locked = true)
/FY 2026-27 -> /04 - April 2026 (auto on 1st of month) -> /Bills & Vouchers, /Operations & Production Runs (per run), /Payroll & Statutory Challans, /[custom monthly folders from templates]
/Master Library -> /ISO Quality Manual & Approved SOPs, /Stock Item Drawings & Engineering Specs, /Calibration & Equipment Certificates, /Internal Report & Document Templates
## 2. Routes
* `/documents` Explorer (tree, grid, preview/version/approval/audit drawer)
* `/documents/editor/new` & `/:docId` Report builder (templates with tokens like item.name, run.period, step.qc_readings, accounts.unit_cost OR blank ad-hoc; pdf/docx export)
* `/documents/scan` Camera scanner & upload (edge detection, crop, enhance, multipage PDF, OCR)
* `/documents/templates` Tab 1 report templates (system: Incoming Inspection, First Article Inspection, NCR/CAPA Form, Batch Summary + custom builder); Tab 2 monthly auto-folder rules
## 3. ISO 7.5 lifecycle: DRAFT -> UNDER_REVIEW -> APPROVED -> OBSOLETE; Prepared -> Reviewed -> Approved (stamps name, role, time, revision; superseded archived/watermarked).
