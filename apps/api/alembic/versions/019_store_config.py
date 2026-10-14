"""Add store_config singleton for admin-editable store settings.

Revision ID: 019_store_config
Revises: 018_employees
Create Date: 2026-10-12
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "019_store_config"
down_revision: str | None = "018_employees"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "store_config",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("business_name", sa.String(length=200), nullable=False, server_default="GEMA Technology"),
        sa.Column("business_ruc", sa.String(length=30), nullable=False, server_default=""),
        sa.Column("business_phone", sa.String(length=40), nullable=False, server_default=""),
        sa.Column("business_address", sa.String(length=300), nullable=False, server_default=""),
        sa.Column("business_email", sa.String(length=320), nullable=False, server_default=""),
        sa.Column("bank_name", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("bank_account_type", sa.String(length=30), nullable=False, server_default="Ahorros"),
        sa.Column("bank_account_number", sa.String(length=60), nullable=False, server_default=""),
        sa.Column("bank_account_holder", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("bank_account_id", sa.String(length=40), nullable=False, server_default=""),
        sa.Column("bank_transfer_instructions", sa.Text(), nullable=False, server_default=""),
        sa.Column("shipping_enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("shipping_flat_rate", sa.Numeric(14, 4), nullable=False, server_default="5.0000"),
        sa.Column("shipping_free_threshold", sa.Numeric(14, 4), nullable=True),
        sa.Column("shipping_province_rates", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("store_config")
