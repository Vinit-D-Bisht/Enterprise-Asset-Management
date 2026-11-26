"""add departments and optional user department links

Revision ID: d923af102c41
Revises: b5081ca95288
Create Date: 2026-11-25 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "d923af102c41"
down_revision: Union[str, None] = "b5081ca95288"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "departments",
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_departments_name_lower",
        "departments",
        [sa.text("lower(trim(name))")],
        unique=True,
    )
    # Batch mode emits normal ALTER statements on PostgreSQL and recreates the
    # table on SQLite, which cannot add a foreign-key constraint directly.
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("department_id", sa.Uuid(), nullable=True))
        batch_op.create_foreign_key(
            "fk_users_department_id_departments",
            "departments",
            ["department_id"],
            ["id"],
        )
    op.create_index("ix_users_department_id", "users", ["department_id"])


def downgrade() -> None:
    op.drop_index("ix_users_department_id", table_name="users")
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint(
            "fk_users_department_id_departments", type_="foreignkey"
        )
        batch_op.drop_column("department_id")
    op.drop_index("uq_departments_name_lower", table_name="departments")
    op.drop_table("departments")
