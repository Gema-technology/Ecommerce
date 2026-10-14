"""Create locations, inventory, and inventory_movements tables.

Revision ID: 004_inventory
Revises: 003_suppliers
Create Date: 2026-07-28
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "004_inventory"
down_revision: str | None = "003_suppliers"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "locations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("city", sa.String(length=100), nullable=True),
        sa.Column("province", sa.String(length=100), nullable=True),
        sa.Column("country", sa.String(length=100), server_default="Ecuador", nullable=False),
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
        sa.UniqueConstraint("code", name="uq_locations_code"),
    )
    op.create_index("ix_locations_code", "locations", ["code"], unique=True)

    op.create_table(
        "inventory",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("location_id", sa.Uuid(), nullable=False),
        sa.Column("quantity", sa.Integer(), server_default="0", nullable=False),
        sa.Column("reserved_quantity", sa.Integer(), server_default="0", nullable=False),
        sa.Column("reorder_point", sa.Integer(), server_default="0", nullable=False),
        sa.Column("reorder_quantity", sa.Integer(), server_default="0", nullable=False),
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
        sa.CheckConstraint("quantity >= 0", name="ck_inventory_quantity_nonneg"),
        sa.CheckConstraint("reserved_quantity >= 0", name="ck_inventory_reserved_nonneg"),
        sa.CheckConstraint(
            "reserved_quantity <= quantity",
            name="ck_inventory_reserved_lte_quantity",
        ),
        sa.CheckConstraint("reorder_point >= 0", name="ck_inventory_reorder_point_nonneg"),
        sa.CheckConstraint("reorder_quantity >= 0", name="ck_inventory_reorder_qty_nonneg"),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("product_id", "location_id", name="uq_inventory_product_location"),
    )
    op.create_index("ix_inventory_product_id", "inventory", ["product_id"], unique=False)
    op.create_index("ix_inventory_location_id", "inventory", ["location_id"], unique=False)
    op.create_index("ix_inventory_quantity", "inventory", ["quantity"], unique=False)
    op.create_index(
        "ix_inventory_reserved_quantity", "inventory", ["reserved_quantity"], unique=False
    )

    op.create_table(
        "inventory_movements",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("inventory_id", sa.Uuid(), nullable=False),
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("direction", sa.String(length=3), nullable=False),
        sa.Column("reference_type", sa.String(length=50), nullable=True),
        sa.Column("reference_id", sa.String(length=100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("quantity > 0", name="ck_inventory_movements_quantity_positive"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["inventory_id"], ["inventory.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_inventory_movements_inventory_id",
        "inventory_movements",
        ["inventory_id"],
        unique=False,
    )
    op.create_index("ix_inventory_movements_type", "inventory_movements", ["type"], unique=False)
    op.create_index(
        "ix_inventory_movements_created_at",
        "inventory_movements",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "ix_inventory_movements_created_by",
        "inventory_movements",
        ["created_by"],
        unique=False,
    )

    # Default development warehouse (Ibarra)
    op.execute(
        sa.text(
            """
            INSERT INTO locations (id, name, code, description, city, province, country, is_active)
            VALUES (
                'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee',
                'Bodega Principal',
                'MAIN',
                'Ubicación principal de desarrollo',
                'Ibarra',
                'Imbabura',
                'Ecuador',
                true
            )
            """
        )
    )


def downgrade() -> None:
    op.drop_index("ix_inventory_movements_created_by", table_name="inventory_movements")
    op.drop_index("ix_inventory_movements_created_at", table_name="inventory_movements")
    op.drop_index("ix_inventory_movements_type", table_name="inventory_movements")
    op.drop_index("ix_inventory_movements_inventory_id", table_name="inventory_movements")
    op.drop_table("inventory_movements")
    op.drop_index("ix_inventory_reserved_quantity", table_name="inventory")
    op.drop_index("ix_inventory_quantity", table_name="inventory")
    op.drop_index("ix_inventory_location_id", table_name="inventory")
    op.drop_index("ix_inventory_product_id", table_name="inventory")
    op.drop_table("inventory")
    op.drop_index("ix_locations_code", table_name="locations")
    op.drop_table("locations")
