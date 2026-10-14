#!/bin/sh
# API container entrypoint. Does NOT run Alembic — migrate as a one-shot job.
# See docs/ops/staging-runbook.md
set -eu
exec "$@"
