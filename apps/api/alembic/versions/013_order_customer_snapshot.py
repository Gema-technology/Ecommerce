"""Order customer snapshot fields for historical accuracy.

Revision ID: 013_order_customer_snapshot
Revises: 012_quotes_module
Create Date: 2026-09-01
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "013_order_customer_snapshot"
down_revision: str | None = "012_quotes_module"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "orders",
        sa.Column("customer_email", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "orders",
        sa.Column("customer_name", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "orders",
        sa.Column("customer_phone", sa.String(length=30), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("orders", "customer_phone")
    op.drop_column("orders", "customer_name")
    op.drop_column("orders", "customer_email")
