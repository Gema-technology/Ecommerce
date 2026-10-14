"""Add employees table and backfill existing staff users.

Revision ID: 018_employees
Revises: 017_user_allow_cash_on_delivery
Create Date: 2026-10-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision: str = "018_employees"
down_revision: str | None = "017_user_allow_cash_on_delivery"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "employees",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("job_title", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("invited_by_user_id", UUID(as_uuid=True), nullable=True),
        sa.Column("invite_token_hash", sa.String(length=64), nullable=True),
        sa.Column("invite_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invited_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("user_id", name="uq_employees_user_id"),
    )
    op.create_index("ix_employees_status", "employees", ["status"])
    op.create_index("ix_employees_invite_token_hash", "employees", ["invite_token_hash"])

    # Backfill: users with ADMIN or SUPER_ADMIN become active employees.
    op.execute(
        """
        INSERT INTO employees (id, user_id, status, accepted_at, created_at, updated_at)
        SELECT gen_random_uuid(), u.id, 'active', now(), now(), now()
        FROM users u
        WHERE EXISTS (
            SELECT 1
            FROM user_roles ur
            JOIN roles r ON r.id = ur.role_id
            WHERE ur.user_id = u.id
              AND r.name IN ('ADMIN', 'SUPER_ADMIN')
        )
        AND NOT EXISTS (
            SELECT 1 FROM employees e WHERE e.user_id = u.id
        )
        """
    )


def downgrade() -> None:
    op.drop_index("ix_employees_invite_token_hash", table_name="employees")
    op.drop_index("ix_employees_status", table_name="employees")
    op.drop_table("employees")
