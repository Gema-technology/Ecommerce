"""Create brand_categories affinity table and backfill from products.

Revision ID: 016_brand_categories
Revises: 015_drop_ai_gateway
Create Date: 2026-10-08
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "016_brand_categories"
down_revision: str | None = "015_drop_ai_gateway"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "brand_categories",
        sa.Column("brand_id", sa.Uuid(), nullable=False),
        sa.Column("category_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("brand_id", "category_id", name="pk_brand_categories"),
    )
    op.create_index(
        "ix_brand_categories_category_id",
        "brand_categories",
        ["category_id"],
        unique=False,
    )

    op.execute(
        """
        INSERT INTO brand_categories (brand_id, category_id)
        SELECT DISTINCT brand_id, category_id
        FROM products
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_index("ix_brand_categories_category_id", table_name="brand_categories")
    op.drop_table("brand_categories")
