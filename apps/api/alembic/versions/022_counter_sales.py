"""Allow orders without a user account for counter sales.

Revision ID: 022_counter_sales
Revises: 021_fulfillment_notify
Create Date: 2026-10-26
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "022_counter_sales"
down_revision: str | None = "021_fulfillment_notify"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("orders", "user_id", existing_type=sa.Uuid(), nullable=True)
    op.add_column(
        "orders",
        sa.Column(
            "channel",
            sa.String(length=20),
            nullable=False,
            server_default="WEB",
        ),
    )


def downgrade() -> None:
    op.drop_column("orders", "channel")
    op.alter_column("orders", "user_id", existing_type=sa.Uuid(), nullable=False)
