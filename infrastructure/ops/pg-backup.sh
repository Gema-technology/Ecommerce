#!/bin/sh
# PostgreSQL logical backup for GEMA staging/production compose stacks.
# Run on the host that can reach the postgres container (Docker network or exec).
#
# Usage examples:
#   ./infrastructure/ops/pg-backup.sh gema-production-postgres-1 /var/backups/gema
#   BACKUP_DIR=/var/backups/gema ./infrastructure/ops/pg-backup.sh <container> <dir>
#
# Never prints POSTGRES_PASSWORD. Restore is documented in docs/ops/production-runbook.md.
set -eu

CONTAINER="${1:?usage: pg-backup.sh <postgres_container> [backup_dir]}"
BACKUP_DIR="${2:-${BACKUP_DIR:-./backups}}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="${BACKUP_DIR}/gema-${STAMP}.sql.gz"

mkdir -p "$BACKUP_DIR"

# Credentials come from the container env (set by compose); not echoed here.
docker exec "$CONTAINER" \
  sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --format=plain' \
  | gzip -c > "$OUT"

echo "backup ok path=${OUT}"
