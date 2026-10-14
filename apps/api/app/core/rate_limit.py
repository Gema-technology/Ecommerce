"""Auth rate limiters — process-local or Redis-shared sliding window."""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from threading import Lock
from typing import Any, Protocol

from fastapi import HTTPException, status

from app.core.config import settings

logger = logging.getLogger(__name__)


class RateLimiter(Protocol):
    def check(self, key: str, *, limit: int, window_seconds: float) -> None: ...

    def reset_for_tests(self) -> None: ...


class SlidingWindowRateLimiter:
    """Process-local sliding-window limiter."""

    def __init__(self) -> None:
        self._buckets: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    def check(self, key: str, *, limit: int, window_seconds: float) -> None:
        if limit <= 0:
            return
        now = time.monotonic()
        with self._lock:
            stamps = [t for t in self._buckets[key] if now - t < window_seconds]
            if len(stamps) >= limit:
                self._buckets[key] = stamps
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests. Try again later.",
                )
            stamps.append(now)
            self._buckets[key] = stamps

    def reset_for_tests(self) -> None:
        with self._lock:
            self._buckets.clear()


_REDIS_SLIDING_WINDOW_LUA = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window_start = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local member = ARGV[4]
local ttl = tonumber(ARGV[5])
redis.call('ZREMRANGEBYSCORE', key, 0, window_start)
local count = redis.call('ZCARD', key)
if count >= limit then
  return 0
end
redis.call('ZADD', key, now, member)
redis.call('EXPIRE', key, ttl)
return 1
"""


class RedisSlidingWindowRateLimiter:
    """Sliding-window limiter shared across processes via Redis ZSET.

    On Redis failure:
    - staging/production → fail-closed (503) so auth brute-force protection is not dropped
    - development/test → fail-open (allow) so local Redis outages do not block dev
    Failures are logged without keys/tokens.
    """

    KEY_PREFIX = "gema:auth_rl:"

    def __init__(self, client: Any) -> None:
        self._client = client

    def _key(self, key: str) -> str:
        return f"{self.KEY_PREFIX}{key}"

    def check(self, key: str, *, limit: int, window_seconds: float) -> None:
        if limit <= 0:
            return
        now = time.time()
        window_start = now - window_seconds
        redis_key = self._key(key)
        member = f"{now}:{time.time_ns()}"
        ttl = max(1, int(window_seconds) + 1)
        try:
            allowed = self._client.eval(
                _REDIS_SLIDING_WINDOW_LUA,
                1,
                redis_key,
                now,
                window_start,
                limit,
                member,
                ttl,
            )
        except Exception:
            if settings.auth_rate_limit_fail_closed:
                logger.error(
                    "Auth rate limiter Redis unavailable in %s; rejecting request",
                    settings.app_env,
                )
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Authentication temporarily unavailable. Try again later.",
                ) from None
            logger.warning(
                "Auth rate limiter Redis unavailable; allowing request (fail-open, non-production)"
            )
            return

        if int(allowed) != 1:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Try again later.",
            )

    def reset_for_tests(self) -> None:
        try:
            keys = list(self._client.scan_iter(match=f"{self.KEY_PREFIX}*", count=100))
            if keys:
                self._client.delete(*keys)
        except Exception:  # noqa: BLE001
            pass


_auth_rate_limiter: RateLimiter | None = None


def _build_auth_rate_limiter() -> RateLimiter:
    backend = settings.effective_auth_rate_limit_backend
    if backend == "redis":
        from app.core.redis_client import get_redis_client

        try:
            client = get_redis_client(ping=True)
            logger.info("Auth rate limiter backend: redis")
            return RedisSlidingWindowRateLimiter(client)
        except Exception:
            if settings.auth_rate_limit_fail_closed:
                raise RuntimeError(
                    "Auth rate limiting requires Redis in staging/production but Redis is unavailable"
                ) from None
            logger.warning(
                "AUTH_RATE_LIMIT_BACKEND=redis unavailable; falling back to memory (non-production)"
            )
            return SlidingWindowRateLimiter()
    return SlidingWindowRateLimiter()


def get_auth_rate_limiter() -> RateLimiter:
    global _auth_rate_limiter
    if _auth_rate_limiter is None:
        _auth_rate_limiter = _build_auth_rate_limiter()
    return _auth_rate_limiter


def check_auth_rate_limit(client_key: str) -> None:
    get_auth_rate_limiter().check(
        client_key,
        limit=settings.auth_rate_limit,
        window_seconds=float(settings.auth_rate_limit_window_seconds),
    )


def reset_auth_rate_limiter_for_tests() -> None:
    global _auth_rate_limiter
    if _auth_rate_limiter is not None:
        _auth_rate_limiter.reset_for_tests()
    _auth_rate_limiter = SlidingWindowRateLimiter()


def set_auth_rate_limiter_for_tests(limiter: RateLimiter) -> None:
    global _auth_rate_limiter
    _auth_rate_limiter = limiter
