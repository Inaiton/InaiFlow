"""Accounts + taxation (S2) schema slot — no-op placeholder owned by that stream.

Revision ID: 0002_accounts
Revises: 0001_baseline
"""

from collections.abc import Sequence

revision: str = "0002_accounts"
down_revision: str | None = "0001_baseline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
