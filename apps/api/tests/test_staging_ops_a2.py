"""Sprint A2 — staging Settings gates, cookie Secure, Redis password wiring."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def _staging_settings(**overrides: Any) -> Settings:
    base: dict[str, Any] = {
        "app_env": "staging",
        "postgres_password": "stage-db-secret-not-default",
        "internal_job_secret": "stage-internal-secret-not-default",
        "payment_webhook_secret": "stage-webhook-secret-not-default",
        "payment_default_provider": "payphone",
        "payphone_token": "stage-payphone-token",
        "payphone_store_id": "stage-payphone-store",
        "payphone_webhook_secret": "stage-payphone-webhook-secret",
        "session_backend": "redis",
        "auth_rate_limit_backend": "redis",
        "public_app_url": "https://staging.example.com",
        "cors_origins": "https://staging.example.com",
        "allow_manual_payment_confirm": False,
    }
    base.update(overrides)
    return Settings(**base)


def test_staging_accepts_secure_sandbox_configuration() -> None:
    cfg = _staging_settings()
    assert cfg.is_staging
    assert cfg.cookie_secure is True
    assert cfg.auth_rate_limit_fail_closed is True
    assert cfg.session_backend == "redis"
    assert cfg.payphone_webhook_secret_required is True
    assert cfg.manual_payment_confirm_allowed is False
    # OpenAPI remains available unless explicitly disabled (unlike production default).
    assert cfg.openapi_docs_enabled is True


def test_staging_rejects_memory_sessions() -> None:
    with pytest.raises(ValidationError):
        _staging_settings(session_backend="memory")


def test_staging_rejects_insecure_internal_secret() -> None:
    with pytest.raises(ValidationError):
        _staging_settings(internal_job_secret="dev-internal-job-secret")


def test_staging_rejects_localhost_public_app_url() -> None:
    with pytest.raises(ValidationError):
        _staging_settings(public_app_url="http://localhost:3000")


def test_staging_rejects_localhost_cors() -> None:
    with pytest.raises(ValidationError):
        _staging_settings(cors_origins="https://staging.example.com,http://localhost:3000")


def test_staging_rejects_payphone_without_token() -> None:
    with pytest.raises(ValidationError):
        _staging_settings(payphone_token="")


def test_staging_allows_manual_provider_with_redis() -> None:
    """Sandbox may still use manual provider; Redis + non-local URLs remain required."""
    cfg = _staging_settings(
        payment_default_provider="manual",
        payphone_token="",
        payphone_store_id="",
        payphone_webhook_secret="",
    )
    assert cfg.payment_default_provider == "manual"
    assert cfg.is_staging


def test_staging_cookie_secure_can_be_overridden_false() -> None:
    """Explicit override for rare HTTP-only lab proxies (not recommended)."""
    cfg = _staging_settings(session_cookie_secure=False)
    assert cfg.cookie_secure is False


def test_redis_password_setting_defaults_empty() -> None:
    cfg = Settings(
        app_env="development",
        redis_password="",
    )
    assert cfg.redis_password == ""


def test_redis_password_setting_accepted() -> None:
    cfg = Settings(
        app_env="development",
        redis_password="stage-redis-secret",
    )
    assert cfg.redis_password == "stage-redis-secret"
