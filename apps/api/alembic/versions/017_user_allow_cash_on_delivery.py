"""Add users.allow_cash_on_delivery for trusted COD customers.

Revision ID: 017_user_allow_cash_on_delivery
Revises: 016_brand_categories
Create Date: 2026-10-12
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "017_user_allow_cash_on_delivery"
down_revision: str | None = "016_brand_categories"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "allow_cash_on_delivery",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "allow_cash_on_delivery")
