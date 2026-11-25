# MODULE 1: ACCOUNTS (`/accounts`)
*Complete TallyPrime-Equivalent Financial Accounting, Inventory Valuation, Indian Taxation & Integrated Payroll*

## 1. Persistent Shell & UX
* **Top Global Bar:** Organization Switcher, Active Financial Year (`FY 2026-27`), **`Alt+G` Universal Command Palette**, and **`Alt+C` Inline Master Creation**.
* **Routes:**
  * `/accounts` — Accounts Gateway & Financial Overview (KPIs, Cash Flow chart, Compliance alerts, Single-key Gateway shortcuts)
  * `/accounts/vouchers/new` — Keyboard-First Voucher Entry Screen (`F4` Contra, `F5` Payment, `F6` Receipt, `F7` Journal, `F8` Sales, `F9` Purchase, `Alt+F5` Debit Note, `Alt+F6` Credit Note, `Alt+F7` Stock/Mfg Journal)
  * `/accounts/vouchers/daybook` — Day Book & Voucher Register (with Edit Log diff viewer)
  * `/accounts/vouchers/orders` — Sales Orders (`Ctrl+F8`), Purchase Orders (`Ctrl+F9`), Receipt/Delivery Notes, Job Work Out/In
  * `/accounts/masters/groups` — 28 Predefined Tally Account Groups + Unlimited Custom Sub-Groups
  * `/accounts/masters/ledgers` — Chart of Accounts (Bill-by-Bill, Credit Limits, MSME 45-day flags, GST/PAN, IFSC, Interest rules)
  * `/accounts/masters/inventory` — Stock Items, Stock Groups/Categories, Godowns, Multi-BOMs, Price Lists, Valuation (`FIFO`, `LIFO`, `Weighted Avg`, `Standard`)
  * `/accounts/masters/cost-centres` — Cost Categories, Cost Centres (auto-synced with Operations Period Runs), and Budgets
  * `/accounts/masters/voucher-types` — Custom Sub-Vouchers, Fiscal Year Numbering Series, Voucher Classes
  * `/accounts/masters/currencies` — Multi-Currency & Forex Gain/Loss rates
  * `/accounts/banking/reconciliation` — Manual & Auto-BRS (CSV, XLSX, MT940, OFX)
  * `/accounts/banking/cheques` — Cheque Register, Cheque Printing, Deposit Slips, Payment Advice
  * `/accounts/payroll/employees` — Employee Master (UAN, ESIC IP, PAN, Bank A/c, Tax Regime), Pay Heads, CTC Templates
  * `/accounts/payroll/attendance` — Attendance, Overtime & Direct Pull of Shop-Floor Production Logs from Operations
  * `/accounts/payroll/pay-runs` — Monthly Payroll Processing, Direct Labor Cost Allocation to Period Runs, Auto-Voucher Posting
  * `/accounts/payroll/statutory` — EPF ECR (`.txt`), ESIC CSV, Professional Tax, LWF, TDS / Form 16, Gratuity
  * `/accounts/taxation/gst` — GSTR-1, GSTR-2A/2B Reconciliation, GSTR-3B JSON Export, GSTR-9, Pre-filing Error Validator
  * `/accounts/taxation/e-compliance` — Direct IRP e-Invoicing (IRN + QR) & e-Way Bill Console
  * `/accounts/taxation/tds-tcs` — Sections `194C/J/I/Q/206C`, `ITNS 281` Challans, `26Q/27Q/27EQ`
  * `/accounts/reports/*` — Balance Sheet (Schedule-III), Profit & Loss A/c, Trial Balance, Cash Flow, Ratio Analysis, Ledgers, Registers, Receivables/Payables Ageing, Stock Summary, Batch Costing
  * `/accounts/utilities/*` — MCA/CARO Immutable Edit Log, Exception Reports, Tally XML Import/Export, Split Financial Year, Group Consolidation

## 2. Automated Payroll-to-Accounting Double-Entry Flow
1. **Salary Accrual (On Payroll Lock):** Debit Direct Labor / Production Wages (tagged to Operations Period Run); Debit Administrative & Office Salaries + Employer EPF/ESIC Contribution; Credit Salary Payable (Net Pay), EPF/ESIC/PT/TDS Payables, Employee Advances/Loans.
2. **Disbursement & Challans (On Bank Payout):** Debit Salary Payable & Statutory Payables; Credit Company Bank Account (matched to bulk NEFT/RTGS payout file).
