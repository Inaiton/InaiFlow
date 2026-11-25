---
name: implementing-tally-accounting
description: Enforces double-entry accounting invariants, Decimal precision, FIFO/Weighted Average inventory valuation, and Indian GST/TDS/Payroll rules in the accounts, taxation, and payroll modules. Use whenever building or changing vouchers, ledgers, inventory valuation, GST/TDS/TCS logic, or payroll runs.
---

# Financial, Tax & Payroll Rules

1. **Exact Numeric Precision:** Always use Python `decimal.Decimal` and PostgreSQL `NUMERIC(18,4)` for currency, tax, and stock quantities. Serialize decimals as strings in JSON. Never use `float`.
2. **Double-Entry Atomicity:** Wrap every voucher creation/edit in a single DB transaction (`async with db.begin():`) verifying `SUM(DR) == SUM(CR)` and updating `bill_allocations` atomically. The deferred `trg_check_voucher_balance` trigger is a backstop, not a substitute for the service check.
3. **GST Split Logic:** Compare supplier `state_code` vs. place-of-supply `state_code`: if equal and non-SEZ, split `50% CGST + 50% SGST`; otherwise apply `100% IGST`. Handle RCM (`is_rcm`) as self-invoice liability.
4. **Statutory Values Are Config, Not Code:** GST slabs, TDS/TCS sections, EPF/ESIC ceilings, PT slabs and income-tax slabs come from `platform_global_configs` with effective dates. Never hard-code rates in business logic; historical vouchers keep the rates in force on their date.
5. **Payroll Cost Allocation:** On Payroll Run lock, compute EPF (`12%` employee; employer `8.33% EPS + 3.67% EPF`, on the ₹15,000 wage ceiling), ESIC (`0.75%` employee / `3.25%` employer, only when gross ≤ ₹21,000), PT, and Section 192 TDS; allocate direct shop-floor wages to linked `period_runs`, and post a balanced Payroll Journal Voucher — all in one transaction.
6. **Cross-Module Posting:** Other modules post vouchers only via `accounts/interface.py` (e.g., `post_system_voucher()`), never by inserting into `vouchers` / `voucher_entries` directly.

## Reference
- Group natures, posting rules, GST/TDS tables, payroll formulas: `docs/specs/07_ACCOUNTING_TAX_PAYROLL_RULES.md` — read only the numbered section you need.
- Tables (`ledgers`, `vouchers`, `voucher_entries`, `payroll_runs`, `payroll_run_lines`): `docs/specs/06_POSTGRES_DATABASE_SCHEMA.sql` sections 3 and 5.
- Payroll lock state machine: `docs/specs/09_API_CONTRACTS_AND_STATE_MACHINES.md` section 2C.
