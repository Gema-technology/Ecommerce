"""Order status history and notification dispatch dedupe.

Revision ID: 021_fulfillment_notify
Revises: 020_sri_fiscal
Create Date: 2026-10-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "021_fulfillment_notify"
down_revision: str | None = "020_sri_fiscal"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "order_status_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("from_status", sa.String(length=30), nullable=False),
        sa.Column("to_status", sa.String(length=30), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_order_status_events_order_id", "order_status_events", ["order_id"]
    )
    op.create_index(
        "ix_order_status_events_created_at", "order_status_events", ["created_at"]
    )

    op.create_table(
        "notification_dispatches",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_key", sa.String(length=64), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False, server_default="email"),
        sa.Column("recipient", sa.String(length=320), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("detail", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "order_id", "event_key", "channel", name="uq_notification_dispatch_once"
        ),
    )
    op.create_index(
        "ix_notification_dispatches_order_id", "notification_dispatches", ["order_id"]
    )
    op.create_index(
        "ix_notification_dispatches_status", "notification_dispatches", ["status"]
    )


def downgrade() -> None:
    op.drop_index("ix_notification_dispatches_status", table_name="notification_dispatches")
    op.drop_index("ix_notification_dispatches_order_id", table_name="notification_dispatches")
    op.drop_table("notification_dispatches")
    op.drop_index("ix_order_status_events_created_at", table_name="order_status_events")
    op.drop_index("ix_order_status_events_order_id", table_name="order_status_events")
    op.drop_table("order_status_events")
