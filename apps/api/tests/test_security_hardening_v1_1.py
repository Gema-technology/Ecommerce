"""Security hardening v1.1 — OpenAPI, secrets, sessions Redis, rate limit, payments."""

from __future__ import annotations

import multiprocessing
import time
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings
from app.core.internal_auth import verify_internal_job_secret
from app.core.rate_limit import (
    RedisSlidingWindowRateLimiter,
    SlidingWindowRateLimiter,
    reset_auth_rate_limiter_for_tests,
    set_auth_rate_limiter_for_tests,
)
from app.core.redis_client import get_redis_client, redis_available, reset_redis_client_for_tests
from app.core.sessions import (
    MemorySessionStore,
    RedisSessionStore,
    get_session_store,
    set_session_store,
)
from app.main import create_app
from app.modules.roles.models import User
from tests.conftest import admin_confirm_payment, login_as
from tests.test_orders_checkout import _login
from tests.test_payments import _checkout_order


def _production_settings(**overrides: Any) -> Settings:
    base = {
        "app_env": "production",
        "postgres_password": "prod-db-secret-not-default",
        "internal_job_secret": "prod-internal-secret-not-default",
        "payment_webhook_secret": "prod-webhook-secret-not-default",
        "payment_default_provider": "payphone",
        "payphone_token": "prod-payphone-token",
        "payphone_store_id": "prod-payphone-store",
        "payphone_webhook_secret": "prod-payphone-webhook-secret",
        "session_backend": "redis",
        "auth_rate_limit_backend": "redis",
        "allow_manual_payment_confirm": False,
        "public_app_url": "https://shop.example.com",
        "cors_origins": "https://shop.example.com",
    }
    base.update(overrides)
    return Settings(**base)


# --- Internal job secret -----------------------------------------------------


def test_internal_secret_compare_accepts_correct(monkeypatch) -> None:
    from app.core import config as config_mod

    monkeypatch.setattr(config_mod.settings, "internal_job_secret", "expected-secret-value")
    verify_internal_job_secret("expected-secret-value")


def test_internal_secret_compare_rejects_wrong(monkeypatch) -> None:
    from fastapi import HTTPException

    from app.core import config as config_mod

    monkeypatch.setattr(config_mod.settings, "internal_job_secret", "expected-secret-value")
    with pytest.raises(HTTPException) as exc:
        verify_internal_job_secret("wrong-secret-value")
    assert exc.value.status_code == 401
    assert "expected-secret" not in str(exc.value.detail)


def test_internal_secret_compare_rejects_missing(monkeypatch) -> None:
    from fastapi import HTTPException

    from app.core import config as config_mod

    monkeypatch.setattr(config_mod.settings, "internal_job_secret", "expected-secret-value")
    with pytest.raises(HTTPException) as exc:
        verify_internal_job_secret(None)
    assert exc.value.status_code == 401


def test_internal_secret_compare_rejects_empty_configured(monkeypatch) -> None:
    from fastapi import HTTPException

    from app.core import config as config_mod

    monkeypatch.setattr(config_mod.settings, "internal_job_secret", "")
    with pytest.raises(HTTPException) as exc:
        verify_internal_job_secret("anything")
    assert exc.value.status_code == 401


def test_internal_secret_compare_rejects_length_mismatch_as_401(monkeypatch) -> None:
    """Unequal lengths must not raise ValueError → unhandled 500."""
    from fastapi import HTTPException

    from app.core import config as config_mod

    monkeypatch.setattr(config_mod.settings, "internal_job_secret", "expected-secret-value")
    with pytest.raises(HTTPException) as exc:
        verify_internal_job_secret("short")
    assert exc.value.status_code == 401


def test_internal_expire_unauthorized_without_header(client: TestClient) -> None:
    client.cookies.clear()
    assert client.post("/api/v1/internal/reservations/expire").status_code == 401


# --- OpenAPI -----------------------------------------------------------------


def test_openapi_enabled_in_development(monkeypatch) -> None:
    from app.core import config as config_mod

    monkeypatch.setattr(config_mod.settings, "app_env", "development")
    monkeypatch.setattr(config_mod.settings, "openapi_enabled", None)
    app = create_app()
    with TestClient(app) as tc:
        assert tc.get("/docs").status_code == 200
        assert tc.get("/redoc").status_code == 200
        assert tc.get("/openapi.json").status_code == 200


def test_openapi_disabled_in_production_by_default(monkeypatch) -> None:
    from app.core import config as config_mod

    monkeypatch.setattr(config_mod.settings, "app_env", "production")
    monkeypatch.setattr(config_mod.settings, "openapi_enabled", None)
    app = create_app()
    with TestClient(app) as tc:
        assert tc.get("/docs").status_code == 404
        assert tc.get("/redoc").status_code == 404
        assert tc.get("/openapi.json").status_code == 404
        assert tc.get("/api/v1/health").status_code == 200


def test_openapi_can_be_explicitly_enabled(monkeypatch) -> None:
    from app.core import config as config_mod

    monkeypatch.setattr(config_mod.settings, "app_env", "production")
    monkeypatch.setattr(config_mod.settings, "openapi_enabled", True)
    app = create_app()
    with TestClient(app) as tc:
        assert tc.get("/docs").status_code == 200


# --- Manual payment confirm --------------------------------------------------


def test_manual_confirm_allowed_in_development(
    client: TestClient,
    customer_user: User,
    admin_user: User,
    monkeypatch,
) -> None:
    from app.core import config as config_mod

    monkeypatch.setattr(config_mod.settings, "app_env", "development")
    monkeypatch.setattr(config_mod.settings, "allow_manual_payment_confirm", None)
    data = _checkout_order(client, customer_user, admin_user, sku="SEC11-DEV")
    _login(client, customer_user)
    payment = client.post(
        f"/api/v1/orders/{data['order']['order_id']}/payment", json={}
    ).json()
    assert admin_confirm_payment(client, admin_user, payment["id"]).status_code == 200


def test_manual_confirm_allowed_in_staging(
    client: TestClient,
    customer_user: User,
    admin_user: User,
    monkeypatch,
) -> None:
    from app.core import config as config_mod

    monkeypatch.setattr(config_mod.settings, "app_env", "staging")
    monkeypatch.setattr(config_mod.settings, "allow_manual_payment_confirm", None)
    data = _checkout_order(client, customer_user, admin_user, sku="SEC11-STG")
    _login(client, customer_user)
    payment = client.post(
        f"/api/v1/orders/{data['order']['order_id']}/payment", json={}
    ).json()
    assert admin_confirm_payment(client, admin_user, payment["id"]).status_code == 200


def test_manual_confirm_blocked_in_production(
    client: TestClient,
    customer_user: User,
    admin_user: User,
    monkeypatch,
) -> None:
    from app.core import config as config_mod

    # Create order/payment while still in development (Secure cookies break TestClient).
    data = _checkout_order(client, customer_user, admin_user, sku="SEC11-PROD")
    _login(client, customer_user)
    payment = client.post(
        f"/api/v1/orders/{data['order']['order_id']}/payment", json={}
    ).json()

    monkeypatch.setattr(config_mod.settings, "app_env", "production")
    monkeypatch.setattr(config_mod.settings, "allow_manual_payment_confirm", None)
    # Keep cookies usable under TestClient (HTTP) while simulating production gates.
    monkeypatch.setattr(config_mod.settings, "session_cookie_secure", False)
    blocked = admin_confirm_payment(client, admin_user, payment["id"])
    assert blocked.status_code == 403


def test_customer_still_cannot_confirm_own_payment(
    client: TestClient,
    customer_user: User,
    admin_user: User,
) -> None:
    data = _checkout_order(client, customer_user, admin_user, sku="SEC11-CUST")
    _login(client, customer_user)
    payment = client.post(
        f"/api/v1/orders/{data['order']['order_id']}/payment", json={}
    ).json()
    assert (
        client.post(f"/api/v1/admin/payments/{payment['id']}/confirm?success=true").status_code
        == 403
    )


# --- Production settings validation ------------------------------------------


def test_production_rejects_insecure_defaults() -> None:
    with pytest.raises(ValidationError):
        Settings(
            app_env="production",
            postgres_password="change_me",
            internal_job_secret="prod-ok",
            payment_webhook_secret="prod-ok-webhook",
            payment_default_provider="stripe",
            session_backend="redis",
            auth_rate_limit_backend="redis",
        )


def test_production_rejects_manual_provider() -> None:
    with pytest.raises(ValidationError):
        _production_settings(payment_default_provider="manual")


def test_production_rejects_memory_sessions() -> None:
    with pytest.raises(ValidationError):
        _production_settings(session_backend="memory")


def test_production_rejects_localhost_public_app_url() -> None:
    with pytest.raises(ValidationError):
        _production_settings(public_app_url="http://localhost:3000")


def test_production_rejects_localhost_cors() -> None:
    with pytest.raises(ValidationError):
        _production_settings(
            cors_origins="https://shop.example.com,http://localhost:3000",
        )


def test_production_accepts_secure_configuration() -> None:
    cfg = _production_settings()
    assert cfg.is_production
    assert not cfg.manual_payment_confirm_allowed
    assert not cfg.openapi_docs_enabled
    assert cfg.public_app_url == "https://shop.example.com"
    assert not cfg._cors_allows_localhost()  # noqa: SLF001


# --- Redis sessions ----------------------------------------------------------


@pytest.fixture()
def redis_or_skip():
    reset_redis_client_for_tests()
    if not redis_available():
        pytest.skip("Redis not available")
    client = get_redis_client(ping=True)
    yield client
    # Cleanup test keys
    for pattern in ("gema:session:test*", "gema:session:*", "gema:auth_rl:test*"):
        keys = list(client.scan_iter(match=pattern, count=100))
        if keys:
            client.delete(*keys)
    reset_redis_client_for_tests()


def test_redis_session_create_get_delete_expire(redis_or_skip) -> None:
    store = RedisSessionStore(redis_or_skip)
    sid = store.create("user-123", ttl_seconds=2)
    data = store.get(sid)
    assert data is not None
    assert data.user_id == "user-123"
    store.delete(sid)
    assert store.get(sid) is None


def test_redis_session_ttl_expires(redis_or_skip) -> None:
    store = RedisSessionStore(redis_or_skip)
    sid = store.create("user-ttl", ttl_seconds=1)
    assert store.get(sid) is not None
    time.sleep(1.5)
    assert store.get(sid) is None


def test_session_backend_redis_does_not_raise_not_implemented(redis_or_skip, monkeypatch) -> None:
    from app.core import config as config_mod
    from app.core import sessions as sessions_mod

    monkeypatch.setattr(config_mod.settings, "session_backend", "redis")
    sessions_mod._session_store = None  # noqa: SLF001
    store = get_session_store()
    assert isinstance(store, RedisSessionStore)
    sid = store.create("u1", ttl_seconds=30)
    assert store.get(sid) is not None
    store.delete(sid)
    set_session_store(MemorySessionStore())


def test_session_backend_redis_unavailable_fails_hard(monkeypatch) -> None:
    from app.core import config as config_mod
    from app.core import sessions as sessions_mod

    monkeypatch.setattr(config_mod.settings, "session_backend", "redis")
    monkeypatch.setattr(config_mod.settings, "redis_host", "127.0.0.1")
    monkeypatch.setattr(config_mod.settings, "redis_port", 1)  # closed port
    sessions_mod._session_store = None  # noqa: SLF001
    reset_redis_client_for_tests()
    with pytest.raises(RuntimeError, match="Redis is unavailable"):
        get_session_store()
    set_session_store(MemorySessionStore())
    reset_redis_client_for_tests()


# --- Redis rate limiting -----------------------------------------------------


def test_redis_rate_limit_blocks_after_limit(redis_or_skip) -> None:
    limiter = RedisSlidingWindowRateLimiter(redis_or_skip)
    key = f"test-{uuid4()}"
    for _ in range(3):
        limiter.check(key, limit=3, window_seconds=60)
    with pytest.raises(Exception) as exc:
        limiter.check(key, limit=3, window_seconds=60)
    assert getattr(exc.value, "status_code", None) == 429
    limiter.reset_for_tests()


def test_redis_rate_limit_fail_closed_in_production(monkeypatch) -> None:
    """Production must not drop brute-force protection when Redis errors at check time."""
    from fastapi import HTTPException

    from app.core import config as config_mod

    class _BrokenRedis:
        def eval(self, *args: Any, **kwargs: Any) -> Any:
            raise ConnectionError("redis down")

    monkeypatch.setattr(config_mod.settings, "app_env", "production")
    limiter = RedisSlidingWindowRateLimiter(_BrokenRedis())
    with pytest.raises(HTTPException) as exc:
        limiter.check("prod-fail-closed", limit=10, window_seconds=60)
    assert exc.value.status_code == 503


def test_redis_rate_limit_fail_closed_in_staging(monkeypatch) -> None:
    """Staging must fail-closed like production when Redis errors at check time."""
    from fastapi import HTTPException

    from app.core import config as config_mod

    class _BrokenRedis:
        def eval(self, *args: Any, **kwargs: Any) -> Any:
            raise ConnectionError("redis down")

    monkeypatch.setattr(config_mod.settings, "app_env", "staging")
    limiter = RedisSlidingWindowRateLimiter(_BrokenRedis())
    with pytest.raises(HTTPException) as exc:
        limiter.check("stage-fail-closed", limit=10, window_seconds=60)
    assert exc.value.status_code == 503


def test_redis_rate_limit_fail_open_outside_production(monkeypatch) -> None:
    from app.core import config as config_mod

    class _BrokenRedis:
        def eval(self, *args: Any, **kwargs: Any) -> Any:
            raise ConnectionError("redis down")

    monkeypatch.setattr(config_mod.settings, "app_env", "development")
    limiter = RedisSlidingWindowRateLimiter(_BrokenRedis())
    limiter.check("dev-fail-open", limit=10, window_seconds=60)


def _redis_rate_limit_worker(host: str, port: int, key: str, limit: int, results: Any) -> None:
    """Child process: hit shared Redis limiter once."""
    import redis
    from fastapi import HTTPException

    client = redis.Redis(host=host, port=port, decode_responses=True)
    limiter = RedisSlidingWindowRateLimiter(client)
    try:
        limiter.check(key, limit=limit, window_seconds=60)
        results.append("ok")
    except HTTPException:
        results.append("429")
    except Exception:
        results.append("err")


def test_redis_rate_limit_shared_across_processes(redis_or_skip) -> None:
    from app.core.config import settings

    key = f"test-mp-{uuid4()}"
    limit = 5
    manager = multiprocessing.Manager()
    results = manager.list()
    procs = [
        multiprocessing.Process(
            target=_redis_rate_limit_worker,
            args=(settings.redis_host, settings.redis_port, key, limit, results),
        )
        for _ in range(limit + 3)
    ]
    for p in procs:
        p.start()
    for p in procs:
        p.join(timeout=10)

    ok_count = list(results).count("ok")
    blocked = list(results).count("429")
    assert ok_count == limit
    assert blocked >= 1
    RedisSlidingWindowRateLimiter(redis_or_skip).reset_for_tests()


def test_memory_rate_limit_still_works_via_reset(
    client: TestClient, customer_user: User, monkeypatch
) -> None:
    from app.core import config as config_mod

    monkeypatch.setattr(config_mod.settings, "auth_rate_limit", 2)
    monkeypatch.setattr(config_mod.settings, "auth_rate_limit_window_seconds", 60)
    reset_auth_rate_limiter_for_tests()
    set_auth_rate_limiter_for_tests(SlidingWindowRateLimiter())

    for _ in range(2):
        assert (
            client.post(
                "/api/v1/auth/login",
                json={"email": customer_user.email, "password": "wrong-password"},
            ).status_code
            == 401
        )
    assert (
        client.post(
            "/api/v1/auth/login",
            json={"email": customer_user.email, "password": "wrong-password"},
        ).status_code
        == 429
    )


# --- Auth regression with session fixture ------------------------------------


def test_login_logout_with_memory_store(client: TestClient, customer_user: User) -> None:
    login_as(client, customer_user)
    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert client.post("/api/v1/auth/logout").status_code == 200
    assert client.get("/api/v1/auth/me").status_code == 401
