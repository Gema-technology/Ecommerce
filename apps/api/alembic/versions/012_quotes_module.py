"""Quote / proforma module tables.

Revision ID: 012_quotes_module
Revises: 011_order_shipping_notes
Create Date: 2026-08-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "012_quotes_module"
down_revision: str | None = "011_order_shipping_notes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "quote_pricing_config",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("min_margin", sa.Numeric(8, 6), nullable=False, server_default="0.12"),
        sa.Column("rec_margin", sa.Numeric(8, 6), nullable=False, server_default="0.20"),
        sa.Column("high_margin", sa.Numeric(8, 6), nullable=False, server_default="0.25"),
        sa.Column("card_cost", sa.Numeric(8, 6), nullable=False, server_default="0.03"),
        sa.Column("default_iva", sa.Numeric(8, 6), nullable=False, server_default="0.15"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute(
        sa.text(
            "INSERT INTO quote_pricing_config (id, min_margin, rec_margin, high_margin, card_cost, default_iva) "
            "VALUES (1, 0.12, 0.20, 0.25, 0.03, 0.15)"
        )
    )

    op.create_table(
        "quote_products",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=True),
        sa.Column("cost_price", sa.Numeric(14, 4), nullable=False),
        sa.Column("other_costs", sa.Numeric(14, 4), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
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
    )
    op.create_index("ix_quote_products_is_active", "quote_products", ["is_active"], unique=False)

    op.create_table(
        "quote_number_counters",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("last_value", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute(sa.text("INSERT INTO quote_number_counters (id, last_value) VALUES (1, 0)"))

    op.create_table(
        "quotes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("number", sa.String(length=20), nullable=False),
        sa.Column("client_name", sa.String(length=200), nullable=False),
        sa.Column("client_id_number", sa.String(length=50), nullable=True),
        sa.Column("client_phone", sa.String(length=50), nullable=True),
        sa.Column("client_email", sa.String(length=120), nullable=True),
        sa.Column("client_address", sa.String(length=250), nullable=True),
        sa.Column("iva_pct", sa.Numeric(8, 6), nullable=False, server_default="0.15"),
        sa.Column("subtotal", sa.Numeric(14, 4), nullable=False, server_default="0"),
        sa.Column("iva_amount", sa.Numeric(14, 4), nullable=False, server_default="0"),
        sa.Column("total", sa.Numeric(14, 4), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("valid_until", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("number"),
    )
    op.create_index("ix_quotes_number", "quotes", ["number"], unique=False)
    op.create_index("ix_quotes_status", "quotes", ["status"], unique=False)
    op.create_index("ix_quotes_created_at", "quotes", ["created_at"], unique=False)
    op.create_index("ix_quotes_created_by", "quotes", ["created_by"], unique=False)

    op.create_table(
        "quote_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quote_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("product_name", sa.String(length=200), nullable=False),
        sa.Column("tier", sa.String(length=10), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("unit_price", sa.Numeric(14, 4), nullable=False),
        sa.Column("line_total", sa.Numeric(14, 4), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["quote_products.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["quote_id"], ["quotes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_quote_items_quote_id", "quote_items", ["quote_id"], unique=False)
    op.create_index("ix_quote_items_product_id", "quote_items", ["product_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_quote_items_product_id", table_name="quote_items")
    op.drop_index("ix_quote_items_quote_id", table_name="quote_items")
    op.drop_table("quote_items")
    op.drop_index("ix_quotes_created_by", table_name="quotes")
    op.drop_index("ix_quotes_created_at", table_name="quotes")
    op.drop_index("ix_quotes_status", table_name="quotes")
    op.drop_index("ix_quotes_number", table_name="quotes")
    op.drop_table("quotes")
    op.drop_table("quote_number_counters")
    op.drop_index("ix_quote_products_is_active", table_name="quote_products")
    op.drop_table("quote_products")
    op.drop_table("quote_pricing_config")
