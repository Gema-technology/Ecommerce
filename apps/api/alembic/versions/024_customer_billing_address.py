"""Store billing address on customers for invoices.

Revision ID: 024_customer_billing_address
Revises: 023_customer_tax_id
Create Date: 2026-10-26
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "024_customer_billing_address"
down_revision: str | None = "023_customer_tax_id"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("address_line", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("address_reference", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("city", sa.String(length=100), nullable=True))
    op.add_column("users", sa.Column("province", sa.String(length=100), nullable=True))
    op.add_column(
        "users",
        sa.Column("country", sa.String(length=100), nullable=False, server_default="Ecuador"),
    )
    op.add_column("users", sa.Column("postal_code", sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "postal_code")
    op.drop_column("users", "country")
    op.drop_column("users", "province")
    op.drop_column("users", "city")
    op.drop_column("users", "address_reference")
    op.drop_column("users", "address_line")
