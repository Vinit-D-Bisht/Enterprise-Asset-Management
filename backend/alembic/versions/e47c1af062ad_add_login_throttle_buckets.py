"""add persistent opaque login throttle buckets

Revision ID: e47c1af062ad
Revises: d923af102c41
Create Date: 2026-11-26 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "e47c1af062ad"
down_revision: Union[str, None] = "d923af102c41"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "login_throttle_buckets",
        sa.Column("bucket_key", sa.String(length=64), nullable=False),
        sa.Column("failure_count", sa.Integer(), nullable=False),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("blocked_until", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "failure_count >= 0", name="ck_login_throttle_failures_nonnegative"
        ),
        sa.PrimaryKeyConstraint("bucket_key"),
    )
    op.create_index(
        "ix_login_throttle_window_started",
        "login_throttle_buckets",
        ["window_started_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_login_throttle_window_started", table_name="login_throttle_buckets"
    )
    op.drop_table("login_throttle_buckets")
