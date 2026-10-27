"""Apply Alembic revisions before the API process starts.

The container entrypoint runs this on every boot. A Postgres advisory lock
serializes replicas so two containers do not migrate at the same time.
``alembic upgrade head`` is a no-op when the database is already current.
"""

from __future__ import annotations

import logging
from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine, text

from alembic import command
from app.core.config import settings

logger = logging.getLogger("gema.upgrade_database")

# Distinct from InventoryService.expire_due_reservations (742653601).
MIGRATION_LOCK_KEY = 742653602


def upgrade_head() -> None:
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    alembic_ini = Path(__file__).resolve().parents[2] / "alembic.ini"
    cfg = Config(str(alembic_ini))

    with engine.connect() as conn:
        locked = conn.dialect.name == "postgresql"
        if locked:
            conn.execute(
                text("SELECT pg_advisory_lock(:key)"),
                {"key": MIGRATION_LOCK_KEY},
            )
            conn.commit()
        try:
            logger.info("alembic upgrade head")
            command.upgrade(cfg, "head")
        finally:
            if locked:
                conn.execute(
                    text("SELECT pg_advisory_unlock(:key)"),
                    {"key": MIGRATION_LOCK_KEY},
                )
                conn.commit()
    engine.dispose()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    upgrade_head()


if __name__ == "__main__":
    main()
