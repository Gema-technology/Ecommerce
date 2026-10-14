"""Create product_prices table.

Revision ID: 005_pricing
Revises: 004_inventory
Create Date: 2026-07-28
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "005_pricing"
down_revision: str | None = "004_inventory"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "product_prices",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("price_type", sa.String(length=20), nullable=False),
        sa.Column("amount", sa.Numeric(precision=14, scale=4), nullable=False),
        sa.Column("currency", sa.String(length=3), server_default="USD", nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("cost_reference", sa.Numeric(precision=14, scale=4), nullable=True),
        sa.Column("supplier_product_id", sa.Uuid(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=False),
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
        sa.CheckConstraint("amount >= 0", name="ck_product_prices_amount_nonneg"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["supplier_product_id"], ["supplier_products.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_product_prices_product_id", "product_prices", ["product_id"], unique=False)
    op.create_index("ix_product_prices_price_type", "product_prices", ["price_type"], unique=False)
    op.create_index("ix_product_prices_is_active", "product_prices", ["is_active"], unique=False)
    op.create_index("ix_product_prices_starts_at", "product_prices", ["starts_at"], unique=False)
    op.create_index("ix_product_prices_ends_at", "product_prices", ["ends_at"], unique=False)
    op.create_index(
        "ix_product_prices_supplier_product_id",
        "product_prices",
        ["supplier_product_id"],
        unique=False,
    )
    op.create_index(
        "ix_product_prices_created_by", "product_prices", ["created_by"], unique=False
    )
    op.create_index(
        "ix_product_prices_lookup",
        "product_prices",
        ["product_id", "price_type", "is_active", "starts_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_product_prices_lookup", table_name="product_prices")
    op.drop_index("ix_product_prices_created_by", table_name="product_prices")
    op.drop_index("ix_product_prices_supplier_product_id", table_name="product_prices")
    op.drop_index("ix_product_prices_ends_at", table_name="product_prices")
    op.drop_index("ix_product_prices_starts_at", table_name="product_prices")
    op.drop_index("ix_product_prices_is_active", table_name="product_prices")
    op.drop_index("ix_product_prices_price_type", table_name="product_prices")
    op.drop_index("ix_product_prices_product_id", table_name="product_prices")
    op.drop_table("product_prices")
