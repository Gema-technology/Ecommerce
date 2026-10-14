"""Create suppliers and supplier_products tables.

Revision ID: 003_suppliers
Revises: 002_product_catalog
Create Date: 2026-07-28
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "003_suppliers"
down_revision: str | None = "002_product_catalog"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "suppliers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("business_name", sa.String(length=255), nullable=False),
        sa.Column("commercial_name", sa.String(length=255), nullable=True),
        sa.Column("tax_id", sa.String(length=50), nullable=False),
        sa.Column("tax_id_type", sa.String(length=20), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("website_url", sa.String(length=500), nullable=True),
        sa.Column("address", sa.String(length=500), nullable=True),
        sa.Column("city", sa.String(length=100), nullable=True),
        sa.Column("province", sa.String(length=100), nullable=True),
        sa.Column("country", sa.String(length=100), server_default="Ecuador", nullable=False),
        sa.Column("contact_name", sa.String(length=150), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tax_id", "tax_id_type", name="uq_suppliers_tax_id_type"),
    )
    op.create_index("ix_suppliers_tax_id", "suppliers", ["tax_id"], unique=False)
    op.create_index("ix_suppliers_is_active", "suppliers", ["is_active"], unique=False)

    op.create_table(
        "supplier_products",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("supplier_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("supplier_sku", sa.String(length=100), nullable=True),
        sa.Column("supplier_product_name", sa.String(length=255), nullable=True),
        sa.Column("cost", sa.Numeric(precision=14, scale=4), nullable=False),
        sa.Column("currency", sa.String(length=3), server_default="USD", nullable=False),
        sa.Column(
            "availability",
            sa.String(length=20),
            server_default="UNKNOWN",
            nullable=False,
        ),
        sa.Column("lead_time_days", sa.Integer(), nullable=True),
        sa.Column(
            "minimum_order_quantity",
            sa.Integer(),
            server_default="1",
            nullable=False,
        ),
        sa.Column("supplier_url", sa.String(length=500), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
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
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("supplier_id", "product_id", name="uq_supplier_products_pair"),
    )
    op.create_index(
        "ix_supplier_products_supplier_id", "supplier_products", ["supplier_id"], unique=False
    )
    op.create_index(
        "ix_supplier_products_product_id", "supplier_products", ["product_id"], unique=False
    )
    op.create_index(
        "ix_supplier_products_availability", "supplier_products", ["availability"], unique=False
    )
    op.create_index(
        "ix_supplier_products_is_active", "supplier_products", ["is_active"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_supplier_products_is_active", table_name="supplier_products")
    op.drop_index("ix_supplier_products_availability", table_name="supplier_products")
    op.drop_index("ix_supplier_products_product_id", table_name="supplier_products")
    op.drop_index("ix_supplier_products_supplier_id", table_name="supplier_products")
    op.drop_table("supplier_products")
    op.drop_index("ix_suppliers_is_active", table_name="suppliers")
    op.drop_index("ix_suppliers_tax_id", table_name="suppliers")
    op.drop_table("suppliers")
