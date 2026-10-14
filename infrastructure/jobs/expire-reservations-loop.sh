#!/bin/sh
# Periodic caller for POST /api/v1/internal/reservations/expire
# Does not print INTERNAL_JOB_SECRET. Safe for Compose / container sidecars.
set -eu

API_ORIGIN="${API_ORIGIN:-http://127.0.0.1:8000}"
INTERVAL="${RESERVATION_EXPIRE_INTERVAL_SECONDS:-300}"
ENABLED="${RESERVATION_EXPIRE_ENABLED:-true}"
URL="${API_ORIGIN%/}/api/v1/internal/reservations/expire"
BODY_FILE="${TMPDIR:-/tmp}/gema-expire-body.json"

if [ "$ENABLED" != "true" ] && [ "$ENABLED" != "1" ]; then
  echo "reservation-expire: disabled (RESERVATION_EXPIRE_ENABLED=${ENABLED})"
  exit 0
fi

if [ -z "${INTERNAL_JOB_SECRET:-}" ]; then
  echo "reservation-expire: INTERNAL_JOB_SECRET is required" >&2
  exit 1
fi

echo "reservation-expire: starting interval=${INTERVAL}s url=${URL}"

TIMEOUT="${RESERVATION_EXPIRE_TIMEOUT_SECONDS:-30}"

while true; do
  code="000"
  # --max-time avoids hanging forever; secret is only in a header (never echoed).
  if code=$(curl -sS --connect-timeout 5 --max-time "$TIMEOUT" \
    -o "$BODY_FILE" -w "%{http_code}" \
    -X POST "$URL" \
    -H "X-GEMA-Internal-Secret: ${INTERNAL_JOB_SECRET}" \
    -H "Accept: application/json"); then
    :
  else
    code="000"
  fi

  if [ "$code" = "200" ]; then
    echo "reservation-expire: ok http=${code} body=$(cat "$BODY_FILE")"
  else
    echo "reservation-expire: failed http=${code}" >&2
  fi

  sleep "$INTERVAL"
done
