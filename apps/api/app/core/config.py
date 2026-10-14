from decimal import Decimal
from pathlib import Path
from typing import Self

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_ROOT_DIR = Path(__file__).resolve().parents[4]
_ENV_FILES = (
    str(_ROOT_DIR / ".env"),
    ".env",
)

# Known insecure placeholders — rejected in production.
_INSECURE_SECRET_VALUES = frozenset(
    {
        "",
        "change_me",
        "changeme",
        "secret",
        "password",
        "dev-internal-job-secret",
        "dev-payment-webhook-secret",
    }
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILES,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    api_port: int = 8000

    postgres_db: str = "gema"
    postgres_user: str = "gema"
    postgres_password: str = "change_me"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    redis_host: str = "localhost"
    redis_port: int = 6379
    # Optional AUTH for Redis (staging/prod). Empty = no password (local only).
    redis_password: str = ""

    cors_origins: str = "http://localhost:3000"
    session_cookie_name: str = "gema_session"
    session_ttl_seconds: int = 60 * 60 * 24 * 7  # 7 days
    session_cookie_secure: bool | None = None  # None → auto from app_env
    session_cookie_samesite: str = "lax"
    session_backend: str = "memory"  # memory | redis

    # OpenAPI /docs /redoc — None → enabled unless production
    openapi_enabled: bool | None = None

    # Auth brute-force protection (per client key / IP)
    auth_rate_limit: int = 10
    auth_rate_limit_window_seconds: int = 60
    # memory | redis — None → follow session_backend
    auth_rate_limit_backend: str | None = None

    # Optional dev admin seed (see app.scripts.seed)
    seed_admin_email: str | None = None
    seed_admin_password: str | None = None

    # Commerce — shipping (MVP) and tax (disabled until fiscal rules defined)
    shipping_enabled: bool = True
    shipping_flat_rate: Decimal = Decimal("5.00")
    shipping_free_threshold: Decimal | None = Decimal("100.00")
    shipping_province_rates: str = ""  # JSON: {"Galápagos": "12.00"}
    commerce_tax_enabled: bool = False
    commerce_tax_rate: Decimal = Decimal("0.15")

    payment_webhook_secret: str = "dev-payment-webhook-secret"
    payment_default_provider: str = "manual"
    # None → allowed in development/staging/test; blocked in production
    allow_manual_payment_confirm: bool | None = None

    # PayPhone (Ecuador) — https://docs.payphone.app/
    payphone_token: str = ""
    payphone_store_id: str = ""
    payphone_api_base: str = "https://pay.payphonetodoesposible.com"
    # Optional shared secret for Notificacion Externa (query ?token= or header)
    payphone_webhook_secret: str = ""

    # Offline bank transfer (Ecuador) — shown to customers; admin confirms deposit
    bank_name: str = ""
    bank_account_type: str = "Ahorros"  # Ahorros | Corriente
    bank_account_number: str = ""
    bank_account_holder: str = ""
    bank_account_id: str = ""  # RUC / CI del titular
    bank_transfer_instructions: str = (
        "Usa el número de orden como referencia. El monto debe coincidir exactamente."
    )

    # Inventory reservation lifecycle
    reservation_ttl_hours: int = 24
    internal_job_secret: str = "dev-internal-job-secret"
    # External scheduler (cron / compose sidecar / python -m app.scripts.expire_reservations)
    # Not used by the FastAPI process itself — documented for ops parity with .env.example.
    reservation_expire_interval_seconds: int = 300
    reservation_expire_enabled: bool = True
    api_origin: str = "http://127.0.0.1:8000"

    # Smart search / sales assist (LLM optional; rules fallback always on)
    ai_enabled: bool = False
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    ai_max_output_tokens: int = 1024
    ai_timeout_seconds: float = 30.0
    search_rate_limit: int = 30  # req/min/IP; 0 = disabled

    # Business info for quote PDFs
    business_name: str = "GEMA Technology"
    business_ruc: str = ""
    business_phone: str = ""
    business_address: str = ""
    business_email: str = ""
    # Optional override; default bundled asset: app/assets/brand/gema_logo.jpg
    business_logo_path: str = ""

    # SRI / facturación electrónica Ecuador
    # Password for the uploaded .p12 — never store in DB
    sri_cert_password: str = ""
    sri_cert_dir: str = "data/sri/certs"
    sri_pdf_dir: str = "data/sri/pdfs"

    # Transactional email (SMTP). Disabled by default — never blocks commerce.
    email_enabled: bool = False
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_use_tls: bool = True
    smtp_timeout_seconds: float = 10.0
    # Storefront base URL used in email links (no secrets).
    public_app_url: str = "http://localhost:3000"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    @property
    def is_staging(self) -> bool:
        return self.app_env.lower() in {"staging", "stage"}

    @property
    def payphone_webhook_secret_required(self) -> bool:
        """Staging/production must authenticate PayPhone Notificacion Externa."""
        return self.is_production or self.is_staging

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def cookie_secure(self) -> bool:
        if self.session_cookie_secure is not None:
            return self.session_cookie_secure
        # Staging and production expect HTTPS-terminated reverse proxies.
        return self.is_production or self.is_staging

    @property
    def openapi_docs_enabled(self) -> bool:
        if self.openapi_enabled is not None:
            return self.openapi_enabled
        return not self.is_production

    @property
    def manual_payment_confirm_allowed(self) -> bool:
        if self.allow_manual_payment_confirm is not None:
            return self.allow_manual_payment_confirm
        return self.app_env.lower() in {
            "development",
            "dev",
            "local",
            "test",
            "testing",
            "staging",
            "stage",
        }

    @property
    def effective_auth_rate_limit_backend(self) -> str:
        if self.auth_rate_limit_backend:
            return self.auth_rate_limit_backend.lower()
        return self.session_backend.lower()

    @property
    def auth_rate_limit_fail_closed(self) -> bool:
        """Fail closed when Redis is down for auth RL in staging/production."""
        return self.is_production or self.is_staging

    def _public_url_is_local(self) -> bool:
        public_url = (self.public_app_url or "").strip().lower()
        return (
            not public_url
            or "localhost" in public_url
            or "127.0.0.1" in public_url
        )

    def _cors_allows_localhost(self) -> bool:
        for origin in self.cors_origin_list:
            lowered = origin.lower()
            if "localhost" in lowered or "127.0.0.1" in lowered:
                return True
        return False

    def _staging_safety_errors(self) -> list[str]:
        """Hard gates for APP_ENV=staging (sandbox PayPhone OK; no local defaults)."""
        errors: list[str] = []
        if self.postgres_password in _INSECURE_SECRET_VALUES:
            errors.append("POSTGRES_PASSWORD must not use a development default in staging")
        if self.internal_job_secret in _INSECURE_SECRET_VALUES:
            errors.append("INTERNAL_JOB_SECRET must not use a development default in staging")
        if self.payment_webhook_secret in _INSECURE_SECRET_VALUES:
            errors.append("PAYMENT_WEBHOOK_SECRET must not use a development default in staging")
        if self.session_backend.lower() == "memory":
            errors.append(
                "SESSION_BACKEND=memory is not allowed in staging; use SESSION_BACKEND=redis"
            )
        if self.effective_auth_rate_limit_backend == "memory":
            errors.append(
                "Auth rate limiting must use Redis in staging "
                "(set AUTH_RATE_LIMIT_BACKEND=redis or SESSION_BACKEND=redis)"
            )
        if self._public_url_is_local():
            errors.append(
                "PUBLIC_APP_URL must be the public staging storefront URL "
                "(not empty, localhost, or 127.0.0.1)"
            )
        if self._cors_allows_localhost():
            errors.append(
                "CORS_ORIGINS must not include localhost/127.0.0.1 in staging "
                "(use the HTTPS staging origin)"
            )
        if self.payment_default_provider.lower() == "payphone":
            if not (self.payphone_token or "").strip():
                errors.append(
                    "PAYPHONE_TOKEN is required in staging when PAYMENT_DEFAULT_PROVIDER=payphone"
                )
            if not (self.payphone_store_id or "").strip():
                errors.append(
                    "PAYPHONE_STORE_ID is required in staging when "
                    "PAYMENT_DEFAULT_PROVIDER=payphone"
                )
        return errors

    @model_validator(mode="after")
    def _enforce_production_safety(self) -> Self:
        errors: list[str] = []

        # Staging/production: PayPhone Notificacion Externa must be authenticated.
        if (
            self.payphone_webhook_secret_required
            and self.payment_default_provider.lower() == "payphone"
            and not (self.payphone_webhook_secret or "").strip()
        ):
            errors.append(
                "PAYPHONE_WEBHOOK_SECRET is required in staging/production when "
                "PAYMENT_DEFAULT_PROVIDER=payphone"
            )

        if self.is_staging:
            errors.extend(self._staging_safety_errors())
            if errors:
                raise ValueError("; ".join(errors))
            return self

        if not self.is_production:
            if errors:
                raise ValueError("; ".join(errors))
            return self

        if self.postgres_password in _INSECURE_SECRET_VALUES:
            errors.append("POSTGRES_PASSWORD must not use a development default in production")
        if self.internal_job_secret in _INSECURE_SECRET_VALUES:
            errors.append("INTERNAL_JOB_SECRET must not use a development default in production")
        if self.payment_webhook_secret in _INSECURE_SECRET_VALUES:
            errors.append("PAYMENT_WEBHOOK_SECRET must not use a development default in production")
        if self.payment_default_provider.lower() == "manual":
            errors.append(
                "PAYMENT_DEFAULT_PROVIDER=manual is not allowed in production "
                "(configure a real provider or use staging)"
            )
        if self.payment_default_provider.lower() == "payphone":
            if not (self.payphone_token or "").strip():
                errors.append("PAYPHONE_TOKEN is required when PAYMENT_DEFAULT_PROVIDER=payphone")
            if not (self.payphone_store_id or "").strip():
                errors.append(
                    "PAYPHONE_STORE_ID is required when PAYMENT_DEFAULT_PROVIDER=payphone"
                )
        if self.allow_manual_payment_confirm is True:
            errors.append("ALLOW_MANUAL_PAYMENT_CONFIRM=true is not allowed in production")
        if self.session_backend.lower() == "memory":
            errors.append(
                "SESSION_BACKEND=memory is not allowed in production; use SESSION_BACKEND=redis"
            )
        if self.effective_auth_rate_limit_backend == "memory":
            errors.append(
                "Auth rate limiting must use Redis in production "
                "(set AUTH_RATE_LIMIT_BACKEND=redis or SESSION_BACKEND=redis)"
            )

        if self._public_url_is_local():
            errors.append(
                "PUBLIC_APP_URL must be a public storefront URL in production "
                "(not empty, localhost, or 127.0.0.1)"
            )
        if self._cors_allows_localhost():
            errors.append(
                "CORS_ORIGINS must not include localhost/127.0.0.1 in production "
                "(use the HTTPS production origin)"
            )

        if errors:
            raise ValueError("; ".join(errors))
        return self


settings = Settings()
