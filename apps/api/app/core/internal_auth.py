"""Authentication for internal job endpoints."""

from __future__ import annotations

from fastapi import HTTPException, status

from app.core.config import settings
from app.core.security import secrets_equal


def verify_internal_job_secret(provided: str | None) -> None:
    """Validate X-GEMA-Internal-Secret without leaking timing or secret values."""
    expected = settings.internal_job_secret
    if not expected or not secrets_equal(provided, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid internal job secret",
        )
