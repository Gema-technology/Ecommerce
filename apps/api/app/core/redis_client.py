"""Shared Redis connection helpers."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse, urlunparse

from app.core.config import settings

logger = logging.getLogger(__name__)

_redis_client: Any | None = None


def normalize_redis_url(url: str) -> str:
    """Upstash requires TLS. Convert ``redis://…@*.upstash.io`` → ``rediss://``."""
    u = url.strip()
    if not u:
        return u
    parsed = urlparse(u)
    host = (parsed.hostname or "").lower()
    if host.endswith("upstash.io") and parsed.scheme == "redis":
        return urlunparse(parsed._replace(scheme="rediss"))
    return u


def get_redis_client(*, ping: bool = True) -> Any:
    """Return a shared Redis client. Raises ConnectionError if unavailable.

    Prefers REDIS_URL (Upstash ``rediss://…``). Otherwise uses host/port/password
    with optional REDIS_SSL=true for TLS without a URL.
    """
    global _redis_client
    import redis

    if _redis_client is None:
        url = normalize_redis_url(settings.redis_url or "")
        if url:
            # Upstash closes non-TLS connections immediately ("Connection closed by server").
            _redis_client = redis.Redis.from_url(
                url,
                decode_responses=True,
                socket_connect_timeout=5.0,
                socket_timeout=5.0,
            )
        else:
            password = (settings.redis_password or "").strip() or None
            host = (settings.redis_host or "").lower()
            use_ssl = bool(settings.redis_ssl) or host.endswith("upstash.io")
            _redis_client = redis.Redis(
                host=settings.redis_host,
                port=settings.redis_port,
                password=password,
                ssl=use_ssl,
                decode_responses=True,
                socket_connect_timeout=5.0,
                socket_timeout=5.0,
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
