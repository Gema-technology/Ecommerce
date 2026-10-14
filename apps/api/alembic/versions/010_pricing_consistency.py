"""Add cart quoted prices and order line discounts for pricing consistency.

Revision ID: 010_pricing_consistency
Revises: 009_ai_gateway
Create Date: 2026-07-28
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "010_pricing_consistency"
down_revision: str | None = "009_ai_gateway"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "cart_items",
        sa.Column("quoted_unit_price", sa.Numeric(precision=14, scale=4), nullable=True),
    )
    op.add_column(
        "order_items",
        sa.Column(
            "line_discount",
            sa.Numeric(precision=14, scale=4),
            server_default="0",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("order_items", "line_discount")
    op.drop_column("cart_items", "quoted_unit_price")
