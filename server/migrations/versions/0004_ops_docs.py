"""Operations + documents (S4): ``period_run_cost_lines`` (payroll allocations + run-page postings).

Revision ID: 0004_ops_docs
Revises: 0003_payroll
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_ops_docs"
down_revision: str | None = "0003_payroll"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "inaiflow_app"
GUC = "NULLIF(current_setting('app.current_org_id', true), '')::uuid"
TABLE = "period_run_cost_lines"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("period_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("step_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("voucher_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("entry_type", sa.String(2), nullable=False),
        sa.Column("amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("line_date", sa.Date(), nullable=False),
        sa.Column("particulars", sa.Text(), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE",
                                name=f"fk_{TABLE}_org_id_organizations"),
        sa.ForeignKeyConstraint(["period_run_id"], ["period_runs.id"], ondelete="CASCADE",
                                name=f"fk_{TABLE}_period_run_id_period_runs"),
        sa.ForeignKeyConstraint(["step_id"], ["period_run_steps.id"], ondelete="SET NULL",
                                name=f"fk_{TABLE}_step_id_period_run_steps"),
        sa.ForeignKeyConstraint(["voucher_id"], ["vouchers.id"], ondelete="SET NULL",
                                name=f"fk_{TABLE}_voucher_id_vouchers"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name=f"fk_{TABLE}_created_by_users"),
        sa.PrimaryKeyConstraint("id", name=f"pk_{TABLE}"),
    )  # fmt: skip
    for col in ("org_id", "period_run_id", "step_id", "voucher_id", "created_by"):
        op.create_index(f"ix_{TABLE}_{col}", TABLE, [col])

    owner = op.get_bind().execute(sa.text("SELECT current_user")).scalar_one()
    op.execute(f"ALTER TABLE {TABLE} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {TABLE} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenant_isolation_{TABLE} ON {TABLE} AS PERMISSIVE FOR ALL TO {APP_ROLE} "
        f"USING (org_id = {GUC}) WITH CHECK (org_id = {GUC})"
    )
    op.execute(
        f'CREATE POLICY owner_access_{TABLE} ON {TABLE} AS PERMISSIVE FOR ALL TO "{owner}" USING (true) WITH CHECK (true)'
    )
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {TABLE} TO {APP_ROLE}")


def downgrade() -> None:
    op.drop_table(TABLE)
