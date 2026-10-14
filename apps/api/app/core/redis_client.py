"""Shared Redis connection helpers."""

from __future__ import annotations

import logging
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

_redis_client: Any | None = None


def get_redis_client(*, ping: bool = True) -> Any:
    """Return a shared Redis client. Raises ConnectionError if unavailable."""
    global _redis_client
    import redis

    if _redis_client is None:
        password = (settings.redis_password or "").strip() or None
        _redis_client = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            password=password,
            decode_responses=True,
            socket_connect_timeout=2.0,
            socket_timeout=2.0,
        )
    if ping:
        _redis_client.ping()
    return _redis_client


def reset_redis_client_for_tests() -> None:
    """Drop the shared client (tests only)."""
    global _redis_client
    if _redis_client is not None:
        try:
            _redis_client.close()
        except Exception:  # noqa: BLE001
            pass
    _redis_client = None


def redis_available() -> bool:
    try:
        get_redis_client(ping=True)
        return True
    except Exception:  # noqa: BLE001
        return False
