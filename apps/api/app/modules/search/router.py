from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.rate_limit import SlidingWindowRateLimiter
from app.modules.search.schemas import SearchAssistRequest, SearchAssistResponse
from app.modules.search.service import SearchAssistService

router = APIRouter(prefix="/search", tags=["search"])

_search_rate_limiter = SlidingWindowRateLimiter()


def reset_search_rate_limiter_for_tests() -> None:
    _search_rate_limiter.reset_for_tests()


def _client_key(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


@router.post("/assist", response_model=SearchAssistResponse)
def search_assist(
    payload: SearchAssistRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> SearchAssistResponse:
    _search_rate_limiter.check(
        f"search:{_client_key(request)}",
        limit=settings.search_rate_limit,
        window_seconds=60.0,
    )
    return SearchAssistService(db).assist(payload.query)
