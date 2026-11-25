"""Superadmin (S5) schema slot — no-op placeholder owned by that stream.

Revision ID: 0005_superadmin
Revises: 0004_ops_docs
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_superadmin"
down_revision: str | None = "0004_ops_docs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # TOTP replay guard: last accepted 30-second step per user / platform admin
    op.add_column("users", sa.Column("mfa_last_step", sa.BigInteger(), nullable=True))
    op.add_column("platform_admins", sa.Column("mfa_last_step", sa.BigInteger(), nullable=True))


def downgrade() -> None:
    op.drop_column("platform_admins", "mfa_last_step")
    op.drop_column("users", "mfa_last_step")
