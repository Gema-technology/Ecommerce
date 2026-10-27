"""Store optional cédula or RUC on customers.

Revision ID: 023_customer_tax_id
Revises: 022_counter_sales
Create Date: 2026-10-26
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "023_customer_tax_id"
down_revision: str | None = "022_counter_sales"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("tax_id_type", sa.String(length=20), nullable=True))
    op.add_column("users", sa.Column("tax_id", sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "tax_id")
    op.drop_column("users", "tax_id_type")
