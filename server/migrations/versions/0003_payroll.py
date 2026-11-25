"""Payroll (S3) schema slot — no-op placeholder owned by that stream.

Revision ID: 0003_payroll
Revises: 0002_accounts
"""

from collections.abc import Sequence

revision: str = "0003_payroll"
down_revision: str | None = "0002_accounts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
