"""Add optional image_url to categories (external URL until file hosting exists).

Revision ID: 014_category_image_url
Revises: 013_order_customer_snapshot
Create Date: 2026-10-08
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "014_category_image_url"
down_revision: str | None = "013_order_customer_snapshot"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "categories",
        sa.Column("image_url", sa.String(length=500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("categories", "image_url")
