# CROSS-MODULE INTEGRATION MATRIX
| Trigger | Source | Effect |
|---|---|---|
| Create Organization | Organization | Seed 28 groups, GST ledgers, 6 roles, ISO templates, locked FY folder tree |
| Instantiate Period Run | Operations | Create Cost Centre (Accounts) + locked folder /FY/MM - Mon YYYY/Operations & Production Runs/<run_title> |
| Accept/Reject units | Operations | Update WIP/FG/Scrap stock; rejected QC -> NCR |
| Post Dr/Cr or assign voucher in run | Ops<->Accounts | Balanced voucher or link existing voucher to step |
| Lock payroll run | Payroll | Allocate wages to runs, post salary journal, archive payslips |
| Save voucher with scanned bill | Accounts->Documents | File PDF in /FY/Month/Bills & Vouchers linked to voucher |
| Approve ISO doc revision | Documents->Operations | Previous revision OBSOLETE; workflow steps reference new SOP |
