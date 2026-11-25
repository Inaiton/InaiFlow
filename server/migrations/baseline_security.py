"""Part of revision 0001_baseline (frozen — never edit; add new migrations instead).

* role ``inaiflow_app`` (NOLOGIN NOBYPASSRLS) granted to the migrating/connection user
* ENABLE + FORCE RLS and ``tenant_isolation_<table>`` (USING + WITH CHECK, TO inaiflow_app) on every table
  with ``org_id`` (+ ``organizations`` keyed by ``id``)
* ``owner_access_<table>`` policy for the connection user so platform/identity/admin/cron paths (which do
  not ``SET ROLE``) keep working under FORCE RLS. The app MUST connect as the role that ran this migration.
* grants, append-only audit triggers, deferred double-entry trigger, seed configs + plans
"""

from __future__ import annotations

import json

import sqlalchemy as sa
from alembic import op

APP_ROLE = "inaiflow_app"
GUC = "NULLIF(current_setting('app.current_org_id', true), '')::uuid"

# tenant tables with a narrower grant than full CRUD
SPECIAL_GRANTS = {
    "organizations": "SELECT, INSERT, UPDATE",
    "org_audit_logs": "SELECT, INSERT",
    "platform_subscription_invoices": "SELECT",
    "platform_impersonation_sessions": None,  # no access for the app role
}
READ_ONLY_PLATFORM = ["platform_global_configs", "platform_global_config_versions", "platform_subscription_plans"]
USER_COLUMNS = (
    "id, email, full_name, mobile, professional_reg_no, avatar_url, digital_signature_url, "
    "avatar_storage_key, signature_storage_key, is_email_verified, mfa_enabled, is_suspended, created_at"
)


def _tenant_tables(conn: sa.Connection) -> list[str]:
    rows = conn.execute(
        sa.text(
            "SELECT c.table_name FROM information_schema.columns c "
            "JOIN information_schema.tables t ON t.table_name = c.table_name AND t.table_schema = c.table_schema "
            "WHERE c.table_schema = 'public' AND c.column_name = 'org_id' AND t.table_type = 'BASE TABLE' "
            "ORDER BY c.table_name"
        )
    ).scalars()
    return list(rows)


def apply_security() -> None:
    conn = op.get_bind()
    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{APP_ROLE}') THEN
                BEGIN
                    CREATE ROLE {APP_ROLE} NOLOGIN NOBYPASSRLS;
                EXCEPTION WHEN insufficient_privilege THEN
                    RAISE EXCEPTION 'role {APP_ROLE} is missing and current_user cannot create it';
                END;
            END IF;
            IF NOT pg_has_role(current_user, '{APP_ROLE}', 'MEMBER') THEN
                BEGIN
                    EXECUTE format('GRANT {APP_ROLE} TO %I', current_user);
                EXCEPTION WHEN insufficient_privilege THEN
                    RAISE EXCEPTION 'cannot grant {APP_ROLE} to %', current_user;
                END;
            END IF;
        END $$;
        """
    )
    op.execute(f"GRANT USAGE ON SCHEMA public TO {APP_ROLE}")
    owner = conn.execute(sa.text("SELECT current_user")).scalar_one()

    tables = _tenant_tables(conn)
    tables_all = ["organizations", *tables]
    for t in tables_all:
        key = "id" if t == "organizations" else "org_id"
        op.execute(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {t} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation_{t} ON {t} AS PERMISSIVE FOR ALL TO {APP_ROLE} "
            f"USING ({key} = {GUC}) WITH CHECK ({key} = {GUC})"
        )
        op.execute(
            f'CREATE POLICY owner_access_{t} ON {t} AS PERMISSIVE FOR ALL TO "{owner}" USING (true) WITH CHECK (true)'
        )
        grant = SPECIAL_GRANTS.get(t, "SELECT, INSERT, UPDATE, DELETE")
        if grant:
            op.execute(f"GRANT {grant} ON {t} TO {APP_ROLE}")

    for t in READ_ONLY_PLATFORM:
        op.execute(f"GRANT SELECT ON {t} TO {APP_ROLE}")
    op.execute(f"GRANT SELECT ({USER_COLUMNS}) ON users TO {APP_ROLE}")

    # Supabase Data API roles must never see these tables.
    op.execute(
        """
        DO $$
        DECLARE r text;
        BEGIN
            FOREACH r IN ARRAY ARRAY['anon', 'authenticated'] LOOP
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r) THEN
                    EXECUTE format('REVOKE ALL ON ALL TABLES IN SCHEMA public FROM %I', r);
                    EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM %I', r);
                END IF;
            END LOOP;
        END $$;
        """
    )

    # Append-only audit logs
    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_audit_mutation() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'audit logs are append-only (% on %)', TG_OP, TG_TABLE_NAME
                USING ERRCODE = 'insufficient_privilege';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    for t in ("org_audit_logs", "platform_audit_logs"):
        op.execute(
            f"CREATE TRIGGER trg_{t}_append_only BEFORE UPDATE OR DELETE ON {t} "
            "FOR EACH ROW EXECUTE FUNCTION prevent_audit_mutation()"
        )

    # Deferred double-entry backstop (spec §7). Non-accounting vouchers carry no ledger entries.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION verify_voucher_double_entry() RETURNS trigger AS $$
        DECLARE
            total_dr NUMERIC(18,4);
            total_cr NUMERIC(18,4);
        BEGIN
            SELECT COALESCE(SUM(amount), 0) INTO total_dr FROM voucher_entries
                WHERE voucher_id = NEW.voucher_id AND entry_type = 'DR';
            SELECT COALESCE(SUM(amount), 0) INTO total_cr FROM voucher_entries
                WHERE voucher_id = NEW.voucher_id AND entry_type = 'CR';
            IF total_dr <> total_cr THEN
                RAISE EXCEPTION 'Double-entry imbalance for voucher %: DR (%) != CR (%)',
                    NEW.voucher_id, total_dr, total_cr;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        "CREATE CONSTRAINT TRIGGER trg_check_voucher_balance AFTER INSERT OR UPDATE ON voucher_entries "
        "DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION verify_voucher_double_entry()"
    )


def drop_security() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_check_voucher_balance ON voucher_entries")
    op.execute("DROP FUNCTION IF EXISTS verify_voucher_double_entry()")
    for t in ("org_audit_logs", "platform_audit_logs"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{t}_append_only ON {t}")
    op.execute("DROP FUNCTION IF EXISTS prevent_audit_mutation()")


def seed_platform_data() -> None:
    from app.seeds import PLANS, SEED_EFFECTIVE_FROM, config_rows

    conn = op.get_bind()
    for plan in PLANS:
        conn.execute(
            sa.text(
                "INSERT INTO platform_subscription_plans (plan_code, name, monthly_price_inr, annual_price_inr, "
                "max_internal_seats, max_external_collaborators, max_storage_gb, enabled_modules) "
                "VALUES (:plan_code, :name, CAST(:monthly AS numeric), CAST(:annual AS numeric), :seats, :ext, "
                ":gb, CAST(:mods AS jsonb)) ON CONFLICT (plan_code) DO NOTHING"
            ),
            {
                "plan_code": plan["plan_code"],
                "name": plan["name"],
                "monthly": plan["monthly_price_inr"],
                "annual": plan["annual_price_inr"],
                "seats": plan["max_internal_seats"],
                "ext": plan["max_external_collaborators"],
                "gb": plan["max_storage_gb"],
                "mods": json.dumps(plan["enabled_modules"]),
            },
        )
    for row in config_rows():
        config_id = conn.execute(
            sa.text(
                "INSERT INTO platform_global_configs (config_category, config_key, display_name, payload, version) "
                "VALUES (:c, :k, :n, CAST(:p AS jsonb), 1) ON CONFLICT (config_category, config_key) DO NOTHING "
                "RETURNING id"
            ),
            {"c": row["category"], "k": row["key"], "n": row["name"], "p": json.dumps(row["payload"])},
        ).scalar()
        if config_id is not None:
            conn.execute(
                sa.text(
                    "INSERT INTO platform_global_config_versions (config_id, version, payload, effective_from, "
                    "change_reason) VALUES (:id, 1, CAST(:p AS jsonb), :ef, 'Initial seed')"
                ),
                {"id": config_id, "p": json.dumps(row["payload"]), "ef": SEED_EFFECTIVE_FROM},
            )
