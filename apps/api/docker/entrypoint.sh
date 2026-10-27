#!/bin/sh
# Apply pending Alembic revisions, then start the process (uvicorn on Render).
# Postgres advisory lock: a second replica waits instead of migrating in parallel.
# SKIP_MIGRATIONS=1 skips this step. The compose migrate job replaces this entrypoint.
set -eu

if [ "${SKIP_MIGRATIONS:-}" != "1" ]; then
  python -m app.scripts.upgrade_database
fi

exec "$@"
