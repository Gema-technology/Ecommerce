"""Add SRI config, fiscal documents, and order buyer identification.

Revision ID: 020_sri_fiscal
Revises: 019_store_config
Create Date: 2026-10-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "020_sri_fiscal"
down_revision: str | None = "019_store_config"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "orders",
        sa.Column("buyer_id_type", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "orders",
        sa.Column("buyer_id_number", sa.String(length=20), nullable=True),
    )

    op.create_table(
        "sri_config",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "tax_regime",
            sa.String(length=40),
            nullable=False,
            server_default="RIMPE_EMPRENDEDOR",
        ),
        sa.Column("ambiente", sa.String(length=1), nullable=False, server_default="1"),
        sa.Column("establecimiento", sa.String(length=3), nullable=False, server_default="001"),
        sa.Column("punto_emision", sa.String(length=3), nullable=False, server_default="001"),
        sa.Column("dir_matriz", sa.String(length=300), nullable=False, server_default=""),
        sa.Column("dir_establecimiento", sa.String(length=300), nullable=False, server_default=""),
        sa.Column(
            "obligado_contabilidad",
            sa.String(length=2),
            nullable=False,
            server_default="NO",
        ),
        sa.Column("contribuyente_especial", sa.String(length=20), nullable=False, server_default=""),
        sa.Column(
            "secuencial_nota_venta",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "secuencial_factura",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("cert_filename", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("cert_stored", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "fiscal_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("doc_type", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("establishment", sa.String(length=3), nullable=False),
        sa.Column("emission_point", sa.String(length=3), nullable=False),
        sa.Column("sequential", sa.Integer(), nullable=False),
        sa.Column("document_number", sa.String(length=20), nullable=False),
        sa.Column("access_key", sa.String(length=49), nullable=True),
        sa.Column("buyer_id_type", sa.String(length=20), nullable=False),
        sa.Column("buyer_id_number", sa.String(length=20), nullable=False),
        sa.Column("buyer_name", sa.String(length=300), nullable=False),
        sa.Column("buyer_email", sa.String(length=320), nullable=True),
        sa.Column("buyer_address", sa.String(length=300), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="USD"),
        sa.Column("subtotal", sa.Numeric(14, 4), nullable=False),
        sa.Column("tax_total", sa.Numeric(14, 4), nullable=False, server_default="0"),
        sa.Column("discount_total", sa.Numeric(14, 4), nullable=False, server_default="0"),
        sa.Column("shipping_total", sa.Numeric(14, 4), nullable=False, server_default="0"),
        sa.Column("total", sa.Numeric(14, 4), nullable=False),
        sa.Column("tax_rate", sa.Numeric(8, 4), nullable=False, server_default="0"),
        sa.Column("xml_unsigned", sa.Text(), nullable=True),
        sa.Column("xml_signed", sa.Text(), nullable=True),
        sa.Column("authorization_number", sa.String(length=49), nullable=True),
        sa.Column("authorized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sri_messages", sa.Text(), nullable=True),
        sa.Column("pdf_path", sa.String(length=500), nullable=True),
        sa.Column("line_items", sa.JSON(), nullable=True),
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
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("access_key", name="uq_fiscal_documents_access_key"),
        sa.UniqueConstraint(
            "doc_type",
            "document_number",
            name="uq_fiscal_documents_doc_number",
        ),
    )
    op.create_index("ix_fiscal_documents_order_id", "fiscal_documents", ["order_id"])
    op.create_index("ix_fiscal_documents_status", "fiscal_documents", ["status"])
    op.create_index("ix_fiscal_documents_doc_type", "fiscal_documents", ["doc_type"])


def downgrade() -> None:
    op.drop_index("ix_fiscal_documents_doc_type", table_name="fiscal_documents")
    op.drop_index("ix_fiscal_documents_status", table_name="fiscal_documents")
    op.drop_index("ix_fiscal_documents_order_id", table_name="fiscal_documents")
    op.drop_table("fiscal_documents")
    op.drop_table("sri_config")
    op.drop_column("orders", "buyer_id_number")
    op.drop_column("orders", "buyer_id_type")
