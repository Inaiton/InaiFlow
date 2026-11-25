-- ============================================================================
-- COMPLETE POSTGRESQL DATABASE SCHEMA (v1.0)
-- Multi-Tenant Cloud ERP: Superadmin + Organization + RBAC + Accounts + Payroll + Operations + Documents
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================================
-- 0. PLATFORM SUPERADMIN & GLOBAL SYSTEM TEMPLATES
-- ============================================================================

CREATE TABLE platform_admins (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL DEFAULT 'SUPERADMIN', -- SUPERADMIN, SUPPORT_ADMIN, BILLING_ADMIN
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    mfa_secret TEXT,
    last_login_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Global Master Seed Configurations edited by Superadmin (Tax Slabs, Account Groups, ISO Templates, Report Templates, Folder Rules)
CREATE TABLE platform_global_configs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    config_category VARCHAR(100) NOT NULL, -- 'ACCOUNT_GROUPS', 'GST_SLABS', 'TDS_SECTIONS', 'PAYROLL_STATUTORY', 'ISO_WORKFLOW_TEMPLATES', 'DOC_REPORT_TEMPLATES', 'FOLDER_TEMPLATES', 'DEFAULT_ROLES', 'FEATURE_FLAGS'
    config_key VARCHAR(150) NOT NULL,
    display_name VARCHAR(255) NOT NULL,
    payload JSONB NOT NULL,
    version INT NOT NULL DEFAULT 1,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    updated_by UUID REFERENCES platform_admins(id),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(config_category, config_key)
);

CREATE TABLE platform_subscription_plans (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    plan_code VARCHAR(50) UNIQUE NOT NULL, -- 'FREE_TRIAL', 'STARTER', 'MANUFACTURING_PRO', 'ENTERPRISE'
    name VARCHAR(100) NOT NULL,
    monthly_price_inr NUMERIC(12,2) NOT NULL,
    annual_price_inr NUMERIC(12,2) NOT NULL,
    max_internal_seats INT NOT NULL,
    max_external_collaborators INT NOT NULL,
    max_storage_gb INT NOT NULL,
    enabled_modules JSONB NOT NULL, -- {"accounts": true, "payroll": true, "operations": true, "documents": true}
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE platform_audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    superadmin_id UUID REFERENCES platform_admins(id),
    action VARCHAR(100) NOT NULL, -- 'UPDATE_TAX_SLAB', 'SUSPEND_ORG', 'IMPERSONATE_ORG', 'UPDATE_GLOBAL_TEMPLATE'
    target_type VARCHAR(100) NOT NULL,
    target_id UUID,
    before_state JSONB,
    after_state JSONB,
    ip_address INET,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- 1. USER-FIRST GLOBAL IDENTITY & MULTI-TENANT ORGANIZATIONS
-- ============================================================================

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash TEXT,
    oauth_provider VARCHAR(50), -- 'LOCAL', 'GOOGLE', 'MICROSOFT'
    oauth_subject_id VARCHAR(255),
    full_name VARCHAR(255) NOT NULL,
    mobile VARCHAR(20),
    avatar_url TEXT,
    digital_signature_url TEXT,
    professional_reg_no VARCHAR(100), -- CA Membership No. or ISO Lead Auditor ID
    is_email_verified BOOLEAN NOT NULL DEFAULT FALSE,
    mfa_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    mfa_secret TEXT,
    is_suspended BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE organizations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_slug VARCHAR(100) UNIQUE NOT NULL,
    public_join_code VARCHAR(20) UNIQUE NOT NULL, -- e.g. 'ORG-8492'
    legal_name VARCHAR(255) NOT NULL,
    mailing_name VARCHAR(255),
    address_line1 TEXT NOT NULL,
    address_line2 TEXT,
    city VARCHAR(100) NOT NULL,
    state_code VARCHAR(5) NOT NULL, -- Indian GST State Code e.g. '33' for Tamil Nadu
    state_name VARCHAR(100) NOT NULL,
    pincode VARCHAR(15) NOT NULL,
    country VARCHAR(100) NOT NULL DEFAULT 'India',
    base_currency_code VARCHAR(10) NOT NULL DEFAULT 'INR',
    base_currency_symbol VARCHAR(10) NOT NULL DEFAULT '₹',
    fy_begins_from DATE NOT NULL,
    books_beginning_from DATE NOT NULL,
    contact_email VARCHAR(255) NOT NULL,
    contact_phone VARCHAR(30) NOT NULL,
    gst_reg_type VARCHAR(50) NOT NULL DEFAULT 'REGULAR', -- 'REGULAR', 'COMPOSITION', 'UNREGISTERED', 'SEZ'
    gstin VARCHAR(15),
    pan VARCHAR(10),
    tan VARCHAR(10),
    cin_or_udyam VARCHAR(50),
    epf_code VARCHAR(50),
    esic_code VARCHAR(50),
    industry_type VARCHAR(100) NOT NULL,
    iso_standard VARCHAR(50) DEFAULT 'ISO_9001_2015',
    logo_url TEXT,
    company_stamp_url TEXT,
    plan_id UUID REFERENCES platform_subscription_plans(id),
    org_status VARCHAR(30) NOT NULL DEFAULT 'ACTIVE', -- 'ACTIVE', 'TRIAL', 'SUSPENDED', 'ARCHIVED'
    security_settings JSONB NOT NULL DEFAULT '{"enforce_2fa_external": true, "session_timeout_mins": 480}'::jsonb,
    owner_user_id UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- 2. GRANULAR RBAC, MEMBERSHIPS, INVITES & RECORD-LEVEL ACL
-- ============================================================================

CREATE TABLE org_roles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    role_code VARCHAR(50) NOT NULL, -- 'ORG_OWNER', 'ADMIN', 'ACCOUNTANT', 'QA_LEAD', 'OPERATOR', 'AUDITOR', or custom
    role_name VARCHAR(100) NOT NULL,
    is_system_role BOOLEAN NOT NULL DEFAULT FALSE,
    is_external_collaborator BOOLEAN NOT NULL DEFAULT FALSE,
    -- Permission Matrix: {"accounts.vouchers": "FULL", "accounts.payroll_runs": "NONE", ...}
    permissions JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(org_id, role_code)
);

CREATE TABLE org_memberships (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_id UUID NOT NULL REFERENCES org_roles(id),
    status VARCHAR(30) NOT NULL DEFAULT 'ACTIVE', -- 'ACTIVE', 'SUSPENDED', 'REVOKED'
    access_expires_at TIMESTAMPTZ, -- Used for time-bound External ISO Auditors
    joined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(org_id, user_id)
);

CREATE TABLE org_invitations_and_requests (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    flow_type VARCHAR(20) NOT NULL, -- 'INVITE_PUSH', 'JOIN_REQUEST_PULL'
    email VARCHAR(255) NOT NULL,
    user_id UUID REFERENCES users(id),
    proposed_role_id UUID REFERENCES org_roles(id),
    token_hash TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING', -- 'PENDING', 'ACCEPTED', 'REJECTED', 'EXPIRED'
    access_expires_at TIMESTAMPTZ,
    created_by UUID REFERENCES users(id),
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE resource_acl (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    subject_type VARCHAR(20) NOT NULL, -- 'ROLE', 'USER'
    subject_id UUID NOT NULL,
    resource_type VARCHAR(50) NOT NULL, -- 'STOCK_ITEM', 'PERIOD_RUN', 'DOC_FOLDER', 'GODOWN'
    resource_id UUID NOT NULL,
    access_level VARCHAR(20) NOT NULL, -- 'NONE', 'READ', 'WRITE', 'FULL'
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(org_id, subject_type, subject_id, resource_type, resource_id)
);

-- ============================================================================
-- 3. ACCOUNTS: MASTERS, DOUBLE-ENTRY VOUCHERS, INVENTORY & BANKING
-- ============================================================================

CREATE TABLE account_groups (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name VARCHAR(150) NOT NULL,
    parent_group_id UUID REFERENCES account_groups(id),
    nature VARCHAR(30) NOT NULL, -- 'ASSETS', 'LIABILITIES', 'INCOME', 'EXPENSES'
    affects_gross_profit BOOLEAN NOT NULL DEFAULT FALSE,
    is_system_group BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE(org_id, name)
);

CREATE TABLE ledgers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    group_id UUID NOT NULL REFERENCES account_groups(id),
    name VARCHAR(200) NOT NULL,
    alias VARCHAR(100),
    currency_code VARCHAR(10) NOT NULL DEFAULT 'INR',
    opening_balance NUMERIC(18,4) NOT NULL DEFAULT 0,
    opening_balance_type VARCHAR(2) NOT NULL DEFAULT 'DR', -- 'DR', 'CR'
    maintain_bill_by_bill BOOLEAN NOT NULL DEFAULT FALSE,
    default_credit_days INT DEFAULT 0,
    credit_limit NUMERIC(18,4),
    party_details JSONB, -- {"gstin", "state_code", "pan", "msme_type", "udyam_no", "bank_account", "ifsc", "address"}
    tax_config JSONB, -- {"tax_type": "GST|TDS|TCS", "gst_head": "CGST|SGST|IGST", "rate": 9.0, "tds_section": "194C"}
    interest_config JSONB,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(org_id, name)
);

CREATE TABLE cost_centres (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    category_name VARCHAR(100) NOT NULL DEFAULT 'Primary Cost Category',
    name VARCHAR(200) NOT NULL,
    parent_id UUID REFERENCES cost_centres(id),
    linked_period_run_id UUID, -- Links directly to period_runs(id)
    budget_amount NUMERIC(18,4),
    UNIQUE(org_id, name)
);

CREATE TABLE voucher_types (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    base_type VARCHAR(50) NOT NULL, -- 'CONTRA', 'PAYMENT', 'RECEIPT', 'JOURNAL', 'SALES', 'PURCHASE', 'CREDIT_NOTE', 'DEBIT_NOTE', 'STOCK_JOURNAL', 'MFG_JOURNAL', 'PAYROLL'
    numbering_method VARCHAR(30) NOT NULL DEFAULT 'AUTOMATIC',
    prefix VARCHAR(30) DEFAULT '',
    suffix VARCHAR(30) DEFAULT '',
    zero_padding INT NOT NULL DEFAULT 4,
    next_number INT NOT NULL DEFAULT 1,
    UNIQUE(org_id, name)
);

CREATE TABLE vouchers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    voucher_type_id UUID NOT NULL REFERENCES voucher_types(id),
    voucher_number VARCHAR(100) NOT NULL,
    voucher_date DATE NOT NULL,
    party_ledger_id UUID REFERENCES ledgers(id),
    supplier_invoice_no VARCHAR(100),
    supplier_invoice_date DATE,
    status VARCHAR(30) NOT NULL DEFAULT 'REGULAR', -- 'REGULAR', 'OPTIONAL', 'MEMORANDUM', 'POST_DATED', 'CANCELLED'
    total_amount NUMERIC(18,4) NOT NULL,
    narration TEXT,
    gst_metadata JSONB, -- {"place_of_supply", "reverse_charge", "irn", "ack_no", "eway_bill_no"}
    linked_period_run_id UUID,
    linked_step_id UUID,
    created_by UUID NOT NULL REFERENCES users(id),
    approved_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(org_id, voucher_type_id, voucher_number)
);

CREATE TABLE voucher_entries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    voucher_id UUID NOT NULL REFERENCES vouchers(id) ON DELETE CASCADE,
    ledger_id UUID NOT NULL REFERENCES ledgers(id),
    entry_type VARCHAR(2) NOT NULL CHECK (entry_type IN ('DR', 'CR')),
    amount NUMERIC(18,4) NOT NULL CHECK (amount >= 0),
    cost_centre_id UUID REFERENCES cost_centres(id),
    bill_allocations JSONB, -- [{"ref_type": "AGAINST_REF", "ref_name": "INV-001", "amount": 50000}]
    bank_reconciliation_date DATE,
    instrument_no VARCHAR(50),
    instrument_date DATE
);

-- ============================================================================
-- 4. INVENTORY, STOCK ITEMS & OPERATIONS (ISO PROCESS CONTROL & PERIOD RUNS)
-- ============================================================================

CREATE TABLE godowns (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name VARCHAR(150) NOT NULL,
    parent_godown_id UUID REFERENCES godowns(id),
    godown_type VARCHAR(50) NOT NULL DEFAULT 'INTERNAL', -- 'INTERNAL', 'WIP', 'SCRAP', 'JOB_WORKER'
    UNIQUE(org_id, name)
);

CREATE TABLE stock_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    target_type VARCHAR(30) NOT NULL DEFAULT 'STOCK_ITEM', -- 'STOCK_ITEM', 'STANDALONE_PROCESS'
    name VARCHAR(200) NOT NULL,
    sku_code VARCHAR(100),
    uom_primary VARCHAR(30) NOT NULL DEFAULT 'Nos',
    uom_alternate VARCHAR(30),
    uom_conversion_factor NUMERIC(18,6),
    valuation_method VARCHAR(30) NOT NULL DEFAULT 'WEIGHTED_AVG', -- 'FIFO', 'LIFO', 'WEIGHTED_AVG', 'STANDARD'
    hsn_sac_code VARCHAR(20),
    gst_rate NUMERIC(5,2) NOT NULL DEFAULT 18.00,
    opening_qty NUMERIC(18,4) NOT NULL DEFAULT 0,
    opening_rate NUMERIC(18,4) NOT NULL DEFAULT 0,
    reorder_level NUMERIC(18,4) DEFAULT 0,
    engineering_diagram_url TEXT,
    custom_fields JSONB NOT NULL DEFAULT '{}'::jsonb, -- e.g. {"alloy_grade": "SS304", "tolerance": "±0.02mm"}
    bom_components JSONB, -- [{"raw_item_id": "...", "qty_per_unit": 1.5, "scrap_pct": 2.0}]
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(org_id, name)
);

CREATE TABLE voucher_inventory_entries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    voucher_id UUID NOT NULL REFERENCES vouchers(id) ON DELETE CASCADE,
    stock_item_id UUID NOT NULL REFERENCES stock_items(id),
    godown_id UUID NOT NULL REFERENCES godowns(id),
    movement_type VARCHAR(10) NOT NULL CHECK (movement_type IN ('INWARD', 'OUTWARD')),
    batch_number VARCHAR(100),
    quantity NUMERIC(18,4) NOT NULL,
    rate NUMERIC(18,4) NOT NULL,
    amount NUMERIC(18,4) NOT NULL,
    gst_rate NUMERIC(5,2) DEFAULT 0
);

CREATE TABLE workflow_templates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    stock_item_id UUID REFERENCES stock_items(id),
    name VARCHAR(200) NOT NULL,
    iso_clause_ref VARCHAR(100),
    version INT NOT NULL DEFAULT 1,
    is_published BOOLEAN NOT NULL DEFAULT FALSE,
    -- React Flow Graph JSON: nodes (OVAL, RECTANGLE, DIAMOND, PARALLEL, TERMINATOR) & edges with conditional rules
    graph_definition JSONB NOT NULL,
    created_by UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE period_runs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    workflow_template_id UUID NOT NULL REFERENCES workflow_templates(id),
    workflow_version INT NOT NULL,
    stock_item_id UUID REFERENCES stock_items(id),
    cost_centre_id UUID REFERENCES cost_centres(id),
    doc_folder_id UUID, -- Auto-created locked folder in Documents
    run_title VARCHAR(200) NOT NULL, -- e.g. 'Component 1 - Sept 2026'
    period_month DATE NOT NULL, -- e.g. '2026-09-01'
    planned_qty NUMERIC(18,4) NOT NULL,
    accepted_qty NUMERIC(18,4) NOT NULL DEFAULT 0,
    rejected_qty NUMERIC(18,4) NOT NULL DEFAULT 0,
    rework_qty NUMERIC(18,4) NOT NULL DEFAULT 0,
    status VARCHAR(30) NOT NULL DEFAULT 'IN_PROGRESS', -- 'PLANNED', 'IN_PROGRESS', 'QC_HOLD', 'COMPLETED', 'CANCELLED'
    total_debit_cost NUMERIC(18,4) NOT NULL DEFAULT 0,
    total_credit_recovery NUMERIC(18,4) NOT NULL DEFAULT 0,
    computed_unit_cost NUMERIC(18,4) NOT NULL DEFAULT 0,
    created_by UUID NOT NULL REFERENCES users(id),
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE period_run_steps (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    period_run_id UUID NOT NULL REFERENCES period_runs(id) ON DELETE CASCADE,
    node_id VARCHAR(100) NOT NULL,
    step_name VARCHAR(200) NOT NULL,
    node_shape VARCHAR(30) NOT NULL, -- 'OVAL', 'RECTANGLE', 'DIAMOND', 'PARALLEL', 'TERMINATOR'
    input_qty NUMERIC(18,4) DEFAULT 0,
    accepted_qty NUMERIC(18,4) DEFAULT 0,
    rejected_qty NUMERIC(18,4) DEFAULT 0,
    qc_measurements JSONB DEFAULT '{}'::jsonb,
    branch_taken VARCHAR(50), -- 'PASS', 'REJECT', 'REWORK'
    status VARCHAR(30) NOT NULL DEFAULT 'PENDING', -- 'PENDING', 'ACTIVE', 'PASSED', 'REJECTED', 'LOCKED'
    is_locked BOOLEAN NOT NULL DEFAULT FALSE,
    signed_off_by UUID REFERENCES users(id),
    signed_off_at TIMESTAMPTZ,
    override_reason TEXT
);

CREATE TABLE iso_ncr_capa_records (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    ncr_number VARCHAR(50) NOT NULL,
    period_run_id UUID REFERENCES period_runs(id),
    run_step_id UUID REFERENCES period_run_steps(id),
    rejected_qty NUMERIC(18,4) NOT NULL,
    defect_description TEXT NOT NULL,
    root_cause_analysis TEXT,
    corrective_action TEXT,
    preventive_action TEXT,
    status VARCHAR(30) NOT NULL DEFAULT 'OPEN', -- 'OPEN', 'INVESTIGATING', 'VERIFIED_CLOSED'
    assigned_to UUID REFERENCES users(id),
    closed_by UUID REFERENCES users(id),
    closed_at TIMESTAMPTZ,
    UNIQUE(org_id, ncr_number)
);

CREATE TABLE calibration_instruments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    instrument_code VARCHAR(100) NOT NULL,
    name VARCHAR(200) NOT NULL,
    last_calibrated_date DATE NOT NULL,
    next_due_date DATE NOT NULL,
    certificate_doc_id UUID,
    status VARCHAR(30) NOT NULL DEFAULT 'VALID', -- 'VALID', 'DUE_SOON', 'EXPIRED'
    UNIQUE(org_id, instrument_code)
);

-- ============================================================================
-- 5. INTEGRATED PAYROLL MANAGEMENT
-- ============================================================================

CREATE TABLE employees (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id), -- Optional link for employee self-service payslip view
    emp_code VARCHAR(50) NOT NULL,
    full_name VARCHAR(200) NOT NULL,
    department VARCHAR(100),
    designation VARCHAR(100),
    employee_category VARCHAR(30) NOT NULL DEFAULT 'STAFF', -- 'SHOP_FLOOR_OPERATOR', 'STAFF', 'MANAGEMENT'
    date_of_joining DATE NOT NULL,
    date_of_exit DATE,
    pan VARCHAR(10),
    uan_epf VARCHAR(20),
    esic_ip_no VARCHAR(20),
    bank_account_no VARCHAR(50),
    bank_ifsc VARCHAR(20),
    tax_regime VARCHAR(20) NOT NULL DEFAULT 'NEW', -- 'NEW', 'OLD'
    salary_structure JSONB NOT NULL, -- {"basic": 25000, "hra": 10000, "special": 5000, "epf_applicable": true, "esic_applicable": false}
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE(org_id, emp_code)
);

CREATE TABLE payroll_runs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    pay_period_month DATE NOT NULL, -- e.g. '2026-09-01'
    status VARCHAR(30) NOT NULL DEFAULT 'DRAFT', -- 'DRAFT', 'LOCKED_POSTED', 'PAID'
    total_gross NUMERIC(18,4) NOT NULL DEFAULT 0,
    total_deductions NUMERIC(18,4) NOT NULL DEFAULT 0,
    total_net_pay NUMERIC(18,4) NOT NULL DEFAULT 0,
    total_employer_contrib NUMERIC(18,4) NOT NULL DEFAULT 0,
    posted_voucher_id UUID REFERENCES vouchers(id),
    locked_by UUID REFERENCES users(id),
    locked_at TIMESTAMPTZ,
    UNIQUE(org_id, pay_period_month)
);

CREATE TABLE payroll_run_lines (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    payroll_run_id UUID NOT NULL REFERENCES payroll_runs(id) ON DELETE CASCADE,
    employee_id UUID NOT NULL REFERENCES employees(id),
    days_worked NUMERIC(5,2) NOT NULL,
    lop_days NUMERIC(5,2) NOT NULL DEFAULT 0,
    overtime_hours NUMERIC(6,2) NOT NULL DEFAULT 0,
    earnings_breakdown JSONB NOT NULL,
    deductions_breakdown JSONB NOT NULL, -- {"epf_emp": 1800, "esic_emp": 0, "pt": 200, "tds": 500}
    employer_contrib_breakdown JSONB NOT NULL, -- {"epf_er": 1800, "esic_er": 0}
    net_pay NUMERIC(18,4) NOT NULL,
    -- Direct labor allocation to Operations Period Runs: [{"period_run_id": "...", "amount": 12000}]
    period_run_allocations JSONB DEFAULT '[]'::jsonb,
    payslip_doc_id UUID
);

-- ============================================================================
-- 6. DOCUMENTS VAULT, TEMPLATES & IMMUTABLE AUDIT TRAIL
-- ============================================================================

CREATE TABLE doc_folders (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    parent_folder_id UUID REFERENCES doc_folders(id) ON DELETE CASCADE,
    name VARCHAR(200) NOT NULL,
    fy_label VARCHAR(20), -- e.g. 'FY 2026-27'
    month_date DATE, -- e.g. '2026-09-01'
    is_system_locked BOOLEAN NOT NULL DEFAULT FALSE, -- TRUE = cannot be deleted or renamed
    linked_period_run_id UUID REFERENCES period_runs(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE doc_templates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    template_type VARCHAR(30) NOT NULL, -- 'REPORT_DOC', 'MONTHLY_FOLDER_RULE'
    name VARCHAR(200) NOT NULL,
    is_system_default BOOLEAN NOT NULL DEFAULT FALSE,
    content_schema JSONB NOT NULL, -- Block layout + {{variable}} tokens OR folder sub-tree definition
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    folder_id UUID NOT NULL REFERENCES doc_folders(id),
    title VARCHAR(255) NOT NULL,
    source_type VARCHAR(30) NOT NULL, -- 'INTERNAL_TEMPLATE', 'BLANK_ADHOC', 'CAMERA_SCAN', 'FILE_UPLOAD', 'AUTO_VOUCHER', 'AUTO_PAYSLIP'
    file_mime_type VARCHAR(100),
    storage_key TEXT, -- S3/R2 object key
    rich_content JSONB, -- Editable JSON blocks for internal docs/reports
    iso_doc_number VARCHAR(100),
    revision_no INT NOT NULL DEFAULT 1,
    approval_status VARCHAR(30) NOT NULL DEFAULT 'DRAFT', -- 'DRAFT', 'UNDER_REVIEW', 'APPROVED', 'OBSOLETE'
    linked_voucher_id UUID REFERENCES vouchers(id),
    linked_period_run_id UUID REFERENCES period_runs(id),
    linked_step_id UUID REFERENCES period_run_steps(id),
    linked_stock_item_id UUID REFERENCES stock_items(id),
    prepared_by UUID NOT NULL REFERENCES users(id),
    reviewed_by UUID REFERENCES users(id),
    approved_by UUID REFERENCES users(id),
    approved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Immutable MCA / CARO & ISO Audit Log (Append-Only)
CREATE TABLE org_audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id),
    user_id UUID NOT NULL REFERENCES users(id),
    role_code VARCHAR(50) NOT NULL,
    module VARCHAR(30) NOT NULL, -- 'ACCOUNTS', 'OPERATIONS', 'DOCUMENTS', 'ORGANIZATION'
    action VARCHAR(30) NOT NULL, -- 'CREATE', 'UPDATE', 'DELETE', 'CANCEL', 'APPROVE', 'LOCK', 'OVERRIDE', 'EXPORT'
    entity_type VARCHAR(100) NOT NULL,
    entity_id UUID NOT NULL,
    before_diff JSONB,
    after_diff JSONB,
    reason TEXT,
    ip_address INET,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- 7. DOUBLE-ENTRY INTEGRITY TRIGGER & ROW-LEVEL SECURITY (RLS)
-- ============================================================================

CREATE OR REPLACE FUNCTION verify_voucher_double_entry() RETURNS TRIGGER AS $$
DECLARE
    total_dr NUMERIC(18,4);
    total_cr NUMERIC(18,4);
BEGIN
    SELECT COALESCE(SUM(amount), 0) INTO total_dr FROM voucher_entries WHERE voucher_id = NEW.voucher_id AND entry_type = 'DR';
    SELECT COALESCE(SUM(amount), 0) INTO total_cr FROM voucher_entries WHERE voucher_id = NEW.voucher_id AND entry_type = 'CR';
    IF total_dr <> total_cr THEN
        RAISE EXCEPTION 'Double-entry imbalance for voucher %: DR (%) != CR (%)', NEW.voucher_id, total_dr, total_cr;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE CONSTRAINT TRIGGER trg_check_voucher_balance
AFTER INSERT OR UPDATE ON voucher_entries
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION verify_voucher_double_entry();

-- Enable Row-Level Security across tenant tables
ALTER TABLE ledgers ENABLE ROW LEVEL SECURITY;
ALTER TABLE vouchers ENABLE ROW LEVEL SECURITY;
ALTER TABLE voucher_entries ENABLE ROW LEVEL SECURITY;
ALTER TABLE stock_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE period_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE employees ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_ledgers ON ledgers USING (org_id = current_setting('app.current_org_id', true)::UUID);
CREATE POLICY tenant_isolation_vouchers ON vouchers USING (org_id = current_setting('app.current_org_id', true)::UUID);
CREATE POLICY tenant_isolation_entries ON voucher_entries USING (org_id = current_setting('app.current_org_id', true)::UUID);
CREATE POLICY tenant_isolation_items ON stock_items USING (org_id = current_setting('app.current_org_id', true)::UUID);
CREATE POLICY tenant_isolation_runs ON period_runs USING (org_id = current_setting('app.current_org_id', true)::UUID);
CREATE POLICY tenant_isolation_employees ON employees USING (org_id = current_setting('app.current_org_id', true)::UUID);
CREATE POLICY tenant_isolation_docs ON documents USING (org_id = current_setting('app.current_org_id', true)::UUID);
