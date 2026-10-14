"""Session store abstraction.

Default backend is in-memory (suitable for single-process and tests).
Use SESSION_BACKEND=redis with a reachable Redis for multi-instance deployments.
"""

from __future__ import annotations

import json
import logging
import secrets
import time
from dataclasses import dataclass
from threading import Lock
from typing import Any, Protocol

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class SessionData:
    user_id: str
    created_at: float
    expires_at: float


class SessionStore(Protocol):
    def create(self, user_id: str, ttl_seconds: int) -> str: ...

    def get(self, session_id: str) -> SessionData | None: ...

    def delete(self, session_id: str) -> None: ...


class MemorySessionStore:
    """Process-local session store. Replace with Redis for multi-instance scale-out."""

    def __init__(self) -> None:
        self._sessions: dict[str, SessionData] = {}
        self._lock = Lock()

    def create(self, user_id: str, ttl_seconds: int) -> str:
        session_id = secrets.token_urlsafe(32)
        now = time.time()
        with self._lock:
            self._sessions[session_id] = SessionData(
                user_id=user_id,
                created_at=now,
                expires_at=now + ttl_seconds,
            )
        return session_id

    def get(self, session_id: str) -> SessionData | None:
        with self._lock:
            data = self._sessions.get(session_id)
            if data is None:
                return None
            if data.expires_at < time.time():
                del self._sessions[session_id]
                return None
            return data

    def delete(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)

    def clear(self) -> None:
        with self._lock:
            self._sessions.clear()


class RedisSessionStore:
    """Redis-backed sessions shared across API processes."""

    KEY_PREFIX = "gema:session:"

    def __init__(self, client: Any) -> None:
        self._client = client

    def _key(self, session_id: str) -> str:
        return f"{self.KEY_PREFIX}{session_id}"

    def create(self, user_id: str, ttl_seconds: int) -> str:
        session_id = secrets.token_urlsafe(32)
        now = time.time()
        payload = {
            "user_id": user_id,
            "created_at": now,
            "expires_at": now + ttl_seconds,
        }
        self._client.set(
            self._key(session_id),
            json.dumps(payload),
            ex=max(1, int(ttl_seconds)),
        )
        return session_id

    def get(self, session_id: str) -> SessionData | None:
        raw = self._client.get(self._key(session_id))
        if raw is None:
            return None
        try:
            payload = json.loads(raw)
            data = SessionData(
                user_id=str(payload["user_id"]),
                created_at=float(payload["created_at"]),
                expires_at=float(payload["expires_at"]),
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            self.delete(session_id)
            return None
        if data.expires_at < time.time():
            self.delete(session_id)
            return None
        return data

    def delete(self, session_id: str) -> None:
        self._client.delete(self._key(session_id))


_session_store: SessionStore | None = None


def get_session_store() -> SessionStore:
    global _session_store
    if _session_store is None:
        backend = settings.session_backend.lower()
        if backend == "redis":
            from app.core.redis_client import get_redis_client

            try:
                client = get_redis_client(ping=True)
            except Exception as exc:
                # Never silently fall back to memory when Redis was requested.
                raise RuntimeError(
                    "SESSION_BACKEND=redis but Redis is unavailable. "
                    "Fix REDIS_HOST/REDIS_PORT or set SESSION_BACKEND=memory for local/dev."
                ) from exc
            _session_store = RedisSessionStore(client)
            logger.info("Session store backend: redis")
        elif backend == "memory":
            _session_store = MemorySessionStore()
            logger.info("Session store backend: memory")
        else:
            raise ValueError(f"Unsupported SESSION_BACKEND={settings.session_backend!r}")
    return _session_store


def set_session_store(store: SessionStore) -> None:
    """Override session store (used by tests)."""
    global _session_store
    _session_store = store
