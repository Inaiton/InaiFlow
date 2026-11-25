# COMPLETE ACCOUNTING, INVENTORY, INDIAN TAXATION & PAYROLL ENGINE RULES
*Reference Specification for Backend Rule Engines (Superadmin-Configurable via `platform_global_configs`)*

---

## 1. Double-Entry Accounting & Balance Rules (28 Standard Tally Groups)

| Primary Group | Nature | Normal Balance | Financial Statement | Gross Profit Impact |
| :--- | :--- | :--- | :--- | :--- |
| Capital Account *(incl. Reserves & Surplus)* | Liabilities | Credit (`CR`) | Balance Sheet | No |
| Loans (Liability) *(Bank OD, Secured, Unsecured)* | Liabilities | Credit (`CR`) | Balance Sheet | No |
| Current Liabilities *(Duties & Taxes, Provisions, Sundry Creditors)* | Liabilities | Credit (`CR`) | Balance Sheet | No |
| Fixed Assets | Assets | Debit (`DR`) | Balance Sheet | No |
| Investments | Assets | Debit (`DR`) | Balance Sheet | No |
| Current Assets *(Stock, Debtors, Cash, Bank, Deposits, Loans & Adv)* | Assets | Debit (`DR`) | Balance Sheet | No |
| Sales Accounts | Income | Credit (`CR`) | Profit & Loss (Trading) | Yes |
| Direct Incomes | Income | Credit (`CR`) | Profit & Loss (Trading) | Yes |
| Indirect Incomes | Income | Credit (`CR`) | Profit & Loss (Net) | No |
| Purchase Accounts | Expenses | Debit (`DR`) | Profit & Loss (Trading) | Yes |
| Direct Expenses *(Manufacturing Wages, Power, Freight Inward)* | Expenses | Debit (`DR`) | Profit & Loss (Trading) | Yes |
| Indirect Expenses *(Admin Salaries, Rent, Audit Fees, Depreciation)* | Expenses | Debit (`DR`) | Profit & Loss (Net) | No |

### Standard Voucher Posting Rules
* **Sales (`F8`):** `DR` Party/Cash/Bank (Invoice Total) | `CR` Sales Account (Taxable Value) | `CR` CGST/SGST/IGST Output Ledgers | `DR/CR` Round-Off.
* **Purchase (`F9`):** `DR` Purchase Account (Taxable Value + Landed Direct Expenses) | `DR` CGST/SGST/IGST Input Tax Credit (ITC) Ledgers | `CR` Supplier/Bank | `CR` TDS Payable (if Section 194Q/194C/194J triggered).
* **Manufacturing Journal (Period Run Closure):**
  * `CR` Raw Material Stock Ledgers (at computed FIFO/Weighted Average consumption rate)
  * `CR` Direct Labor / Production Wages & Direct Overhead Allocation (from Cost Centre)
  * `DR` Finished Goods Stock Ledger (`Total Consumed Cost / Accepted Good Units = Unit Cost`)
  * `DR` Scrap / By-Product Stock Ledger (at net realizable scrap value, reducing Finished Goods unit cost).

---

## 2. Goods & Services Tax (GST) Calculation & Return Rules

### 2.1 Place of Supply & Tax Split Logic
1. **Compare Supplier State Code vs. Place of Supply (Recipient State Code):**
   * **Same State (`supplier_state == pos_state`) & Not SEZ:**
     `CGST = Taxable Value × (GST Rate / 2)`, `SGST = Taxable Value × (GST Rate / 2)`
   * **Different State (`supplier_state != pos_state`) OR SEZ Supply OR Import/Export:**
     `IGST = Taxable Value × GST Rate`
2. **Reverse Charge Mechanism (RCM):**
   * Triggered when `is_rcm = true` (e.g., Goods Transport Agency / GTA @ 5%, Legal Services, Import of Services, or notified Unregistered purchases).
   * Recipient posts self-invoice liability (`DR Tax on RCM` / `CR RCM Output Payable`) and claims eligible ITC upon cash challan payment.
3. **Standard GST Rate Slabs (Editable in Superadmin):** `0% (Exempt/Nil)`, `0.25%`, `3%`, `5%`, `12%`, `18%`, `28%` + Cess (`Ad-valorem %` or `Specific ₹/unit`).

### 2.2 GSTR-1, GSTR-2B Reconciliation & GSTR-3B Mapping
* **GSTR-1 Tables:**
  * `4A/4B`: B2B Invoices (Registered GSTIN recipients)
  * `5A`: B2C Large (Inter-state unregistered invoices > ₹1,00,000)
  * `7`: B2C Others (Consolidated state-wise + rate-wise summary)
  * `9B`: Credit/Debit Notes Registered (`CDNR`) & Unregistered (`CDNUR`)
  * `6A`: Exports (`WPAY` / `WOPAY`)
  * `12`: HSN-wise Summary (Mandatory 4-digit HSN for turnover ≤ ₹5 Cr; 6-digit HSN for turnover > ₹5 Cr)
* **GSTR-2B Reconciliation Buckets:**
  1. *Exact Match:* GSTIN + Invoice No. (normalized alphanumeric) + Invoice Date (±1 day) + Tax Amount (±₹1 tolerance).
  2. *Partial / Tax Mismatch:* Invoice matched, taxable value or tax differs > ₹1.
  3. *Missing in Books:* Present in GSTN GSTR-2B JSON, absent in Purchase Vouchers (hold ITC until recorded).
  4. *Missing in Portal:* Recorded in Purchase Vouchers, not uploaded by supplier in GSTR-1 (flag for vendor follow-up; ineligible for ITC claim in GSTR-3B).
* **e-Invoicing (IRP) & e-Way Bill Rules:**
  * **e-Invoice:** Mandatory for B2B/Export invoices if Aggregate Annual Turnover (AATO) exceeds notified threshold (₹5 Cr+); generates 64-char `IRN` + Signed QR Code.
  * **e-Way Bill:** Mandatory for movement of goods consignment value > **₹50,000** (or state-specific intra-state threshold).

---

## 3. TDS (Tax Deducted at Source) & TCS Rules

| Section | Nature of Payment | Single / Annual Threshold | Rate (With PAN) | Rate (No PAN — Sec 206AA) |
| :--- | :--- | :--- | :--- | :--- |
| **194C** | Contractors / Sub-contractors / Job Work | ₹30,000 single / ₹1,00,000 annual | **1%** (Indiv/HUF) / **2%** (Company/Firm) | **20%** |
| **194J(a)** | Technical Services / Royalty / Call Centre | ₹30,000 annual | **2%** | **20%** |
| **194J(b)** | Professional Services (CA, Legal, Engineering) | ₹30,000 annual | **10%** | **20%** |
| **194I(a)** | Rent of Plant, Machinery or Equipment | ₹2,40,000 annual | **2%** | **20%** |
| **194I(b)** | Rent of Land, Building or Furniture | ₹2,40,000 annual | **10%** | **20%** |
| **194H** | Commission or Brokerage | ₹15,000 annual | **2%** | **20%** |
| **194Q** | Purchase of Goods (Buyer turnover > ₹10 Cr) | ₹50,00,000 annual per seller | **0.1%** on amount > ₹50L | **5%** |
| **206C(1)** | TCS on Scrap Sale | No threshold | **1%** | **5%** |
| **206C(1H)** | TCS on Sale of Goods (if 194Q not applicable) | ₹50,00,000 annual per buyer | **0.1%** on receipt > ₹50L | **1%** |

* **Due Dates:** TDS/TCS deducted in a month must be deposited via `ITNS 281` by the **7th of the following month** (30th April for March). Quarterly returns: `26Q` (Domestic), `27Q` (NRI), `27EQ` (TCS).

---

## 4. Payroll Statutory Calculation Formulas (India)

1. **EPF (Employees' Provident Fund):**
   * *Applicability:* Mandatory if employee count ≥ 20; wage ceiling **₹15,000/month** on `EPF Wages = Basic + DA + Retaining Allowance` (employers may opt for actual Basic).
   * *Employee Share:* **12%** of EPF Wages (deducted from Gross).
   * *Employer Split:* **8.33%** to EPS (capped at ₹1,250/month on ₹15,000 ceiling) + **3.67%** to EPF + **0.50%** EDLI + **0.50%** EPF Admin Charges (min ₹500).
2. **ESIC (Employees' State Insurance):**
   * *Applicability:* Applicable if Gross Monthly Wages ≤ **₹21,000** (₹25,000 for persons with disability).
   * *Employee Share:* **0.75%** of Gross Wages (rounded up to next rupee).
   * *Employer Share:* **3.25%** of Gross Wages.
3. **Professional Tax (PT):**
   * State-specific monthly/half-yearly slab lookup stored in `platform_global_configs` (e.g., Tamil Nadu half-yearly slabs, Maharashtra ₹200/month & ₹300 in Feb, Karnataka ₹200/month for salary ≥ ₹15,000).
4. **Income Tax TDS on Salary (Section 192):**
   * Compute projected annual taxable income (`Annual Gross - Standard Deduction [₹75,000 New Regime / ₹50,000 Old Regime] - Section 80C/80D/HRA exemptions if Old Regime`), apply progressive income tax slabs + 4% Health & Education Cess, subtract YTD TDS already deducted, and divide by remaining months in the Financial Year.
