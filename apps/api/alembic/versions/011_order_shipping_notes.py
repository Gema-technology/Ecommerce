"""Add shipping address and customer notes to orders.

Revision ID: 011_order_shipping_notes
Revises: 010_pricing_consistency
Create Date: 2026-07-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "011_order_shipping_notes"
down_revision: str | None = "010_pricing_consistency"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "orders",
        sa.Column(
            "shipping_address",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=True,
        ),
    )
    op.add_column(
        "orders",
        sa.Column("customer_notes", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("orders", "customer_notes")
    op.drop_column("orders", "shipping_address")
