from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text

from app.core.config import settings

router = APIRouter(prefix="/health", tags=["health"])


class HealthResponse(BaseModel):
    status: str
    service: str


class ReadinessResponse(BaseModel):
    status: str
    service: str
    checks: dict[str, str]


@router.get("", response_model=HealthResponse)
def health_check() -> HealthResponse:
    """Liveness — process is up. Does not verify dependencies."""
    return HealthResponse(status="ok", service="gema-api")


@router.get("/ready", response_model=ReadinessResponse)
def readiness_check() -> ReadinessResponse | JSONResponse:
    """Readiness — PostgreSQL required; Redis required when sessions/rate-limit use it."""
    checks: dict[str, str] = {}
    ok = True

    try:
        from app.core.database import engine

        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["postgres"] = "ok"
    except Exception:
        checks["postgres"] = "unavailable"
        ok = False

    needs_redis = (
        settings.session_backend.lower() == "redis"
        or settings.effective_auth_rate_limit_backend == "redis"
    )
    if needs_redis:
        try:
            from app.core.redis_client import get_redis_client

            get_redis_client(ping=True)
            checks["redis"] = "ok"
        except Exception:
            checks["redis"] = "unavailable"
            ok = False
    else:
        checks["redis"] = "not_required"

    body = ReadinessResponse(
        status="ok" if ok else "unavailable",
        service="gema-api",
        checks=checks,
    )
    if not ok:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=body.model_dump(),
        )
    return body
