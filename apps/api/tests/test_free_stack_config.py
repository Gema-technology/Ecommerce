"""Free-stack PaaS wiring: DATABASE_URL (Supabase) + REDIS_URL (Upstash)."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from app.core import redis_client as redis_mod
from app.core.config import Settings, normalize_database_url, _resolve_env_search_roots


def test_env_search_roots_do_not_indexerror_on_shallow_paths() -> None:
    """Docker image path depth used to crash on parents[4]; must stay import-safe."""
    roots = _resolve_env_search_roots()
    assert roots
    assert all(isinstance(p, Path) for p in roots)
    # Importing Settings must succeed (env files list is built at module load).
    cfg = Settings(app_env="development")
    assert cfg.app_env == "development"


def test_normalize_supabase_url_adds_psycopg_and_ssl() -> None:
    raw = "postgresql://postgres.abc:SecretPass123@aws-0-us-east-1.pooler.supabase.com:6543/postgres"
    out = normalize_database_url(raw)
    assert out.startswith("postgresql+psycopg://")
    assert "sslmode=require" in out
    assert "SecretPass123" in out


def test_normalize_respects_explicit_sslmode() -> None:
    raw = "postgresql://u:p@db.example.com:5432/gema?sslmode=verify-full"
    out = normalize_database_url(raw, sslmode="require")
    assert out.count("sslmode=") == 1
    assert "sslmode=verify-full" in out


def test_normalize_strips_pgbouncer_query_flag() -> None:
    raw = (
        "postgresql://u:p@aws-1.pooler.supabase.com:6543/postgres"
        "?pgbouncer=true&sslmode=require"
    )
    out = normalize_database_url(raw)
    assert "pgbouncer" not in out.lower()
    assert "sslmode=require" in out
    assert out.startswith("postgresql+psycopg://")


def test_database_url_property_uses_env_override() -> None:
    cfg = Settings(
        app_env="development",
        database_url_env=(
            "postgresql://postgres.abc:SupaSecret99@aws-0.pooler.supabase.com:6543/postgres"
        ),
        postgres_password="change_me",
    )
    assert "postgresql+psycopg://" in cfg.database_url
    assert "sslmode=require" in cfg.database_url
    assert not cfg._postgres_secret_insecure()


def test_staging_accepts_database_url_without_discrete_password() -> None:
    cfg = Settings(
        app_env="staging",
        database_url_env=(
            "postgresql://postgres:SupaSecret99@db.xxx.supabase.co:5432/postgres"
        ),
        postgres_password="change_me",  # ignored when DATABASE_URL set
        internal_job_secret="stage-internal-secret-not-default",
        payment_webhook_secret="stage-webhook-secret-not-default",
        payment_default_provider="manual",
        session_backend="redis",
        auth_rate_limit_backend="redis",
        public_app_url="https://gema.vercel.app",
        cors_origins="https://gema.vercel.app",
        redis_url="rediss://default:token@upstash.example:6379",
    )
    assert cfg.is_staging
    assert "supabase.co" in cfg.database_url
    assert cfg.redis_url.startswith("rediss://")


def test_staging_rejects_insecure_database_url_password() -> None:
    with pytest.raises(ValidationError):
        Settings(
            app_env="staging",
            database_url_env="postgresql://postgres:change_me@db.xxx.supabase.co:5432/postgres",
            internal_job_secret="stage-internal-secret-not-default",
            payment_webhook_secret="stage-webhook-secret-not-default",
            payment_default_provider="manual",
            session_backend="redis",
            auth_rate_limit_backend="redis",
            public_app_url="https://gema.vercel.app",
            cors_origins="https://gema.vercel.app",
        )


def test_redis_client_prefers_redis_url(monkeypatch: pytest.MonkeyPatch) -> None:
    redis_mod.reset_redis_client_for_tests()
    fake_client = MagicMock()
    fake_pkg = MagicMock()
    fake_pkg.Redis.from_url.return_value = fake_client
    monkeypatch.setitem(sys.modules, "redis", fake_pkg)
    monkeypatch.setattr(redis_mod.settings, "redis_url", "rediss://default:tok@host:6379")
    client = redis_mod.get_redis_client(ping=True)
    fake_pkg.Redis.from_url.assert_called_once()
    assert "rediss://default:tok@host:6379" in fake_pkg.Redis.from_url.call_args.args
    fake_client.ping.assert_called_once()
    assert client is fake_client
    redis_mod.reset_redis_client_for_tests()
