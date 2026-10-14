"""Call the internal reservation expiry job over HTTP.

This is the host-side scheduler entrypoint. It reuses the existing endpoint and
internal auth; business rules stay in InventoryService.expire_due_reservations.

Usage (from apps/api with venv active):

  # one-shot (cron / systemd timer / CI)
  python -m app.scripts.expire_reservations

  # development loop
  python -m app.scripts.expire_reservations --loop

Environment:
  API_ORIGIN                         default http://127.0.0.1:8000
  INTERNAL_JOB_SECRET                required
  RESERVATION_EXPIRE_INTERVAL_SECONDS  default 300 (loop mode)
  RESERVATION_EXPIRE_ENABLED         default true
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
import urllib.error
import urllib.request

logger = logging.getLogger("gema.expire_reservations")

_DEFAULT_ORIGIN = "http://127.0.0.1:8000"
_DEFAULT_INTERVAL = 300


def _env_bool(name: str, default: bool = True) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return int(raw)


def run_once(*, api_origin: str, secret: str, timeout: float = 30.0) -> int:
    """POST expire job. Returns process exit code. Never logs the secret."""
    url = f"{api_origin.rstrip('/')}/api/v1/internal/reservations/expire"
    request = urllib.request.Request(
        url,
        data=b"",
        method="POST",
        headers={
            "X-GEMA-Internal-Secret": secret,
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            status = response.status
    except urllib.error.HTTPError as exc:
        # Do not include request headers (would leak the secret).
        logger.error("reservation expire failed http=%s", exc.code)
        return 1
    except TimeoutError:
        # urllib raises built-in TimeoutError on read/connect timeout (not URLError).
        logger.error("reservation expire timeout after %ss", timeout)
        return 1
    except urllib.error.URLError as exc:
        logger.error("reservation expire unreachable: %s", exc.reason)
        return 1

    if status != 200:
        logger.error("reservation expire failed http=%s", status)
        return 1

    try:
        payload = json.loads(body) if body else {}
    except json.JSONDecodeError:
        payload = {}

    logger.info(
        "reservation expire ok expired=%s cancelled=%s",
        payload.get("expired_reservations"),
        payload.get("cancelled_orders"),
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="GEMA reservation expiry job caller")
    parser.add_argument(
        "--loop",
        action="store_true",
        help="Repeat on RESERVATION_EXPIRE_INTERVAL_SECONDS (dev / sidecar)",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    if not _env_bool("RESERVATION_EXPIRE_ENABLED", True):
        logger.info("reservation expire disabled (RESERVATION_EXPIRE_ENABLED)")
        return 0

    secret = os.environ.get("INTERNAL_JOB_SECRET", "").strip()
    if not secret:
        logger.error("INTERNAL_JOB_SECRET is required")
        return 1

    api_origin = os.environ.get("API_ORIGIN", _DEFAULT_ORIGIN).strip() or _DEFAULT_ORIGIN
    interval = _env_int("RESERVATION_EXPIRE_INTERVAL_SECONDS", _DEFAULT_INTERVAL)
    if interval < 1:
        logger.error("RESERVATION_EXPIRE_INTERVAL_SECONDS must be >= 1")
        return 1

    if not args.loop:
        return run_once(api_origin=api_origin, secret=secret)

    logger.info(
        "reservation expire loop starting interval=%ss origin=%s",
        interval,
        api_origin,
    )
    while True:
        run_once(api_origin=api_origin, secret=secret)
        time.sleep(interval)


if __name__ == "__main__":
    sys.exit(main())
