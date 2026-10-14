"""Admin ops dashboard routes."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.auth.dependencies import RequireAdmin
from app.modules.ops.schemas import OpsSummaryResponse
from app.modules.ops.service import OpsService

router = APIRouter(tags=["ops"])


@router.get("/admin/ops/summary", response_model=OpsSummaryResponse)
def get_ops_summary(
    _admin: RequireAdmin,
    db: Annotated[Session, Depends(get_db)],
    period: Literal["today", "7d", "30d"] = Query("7d"),
) -> OpsSummaryResponse:
    return OpsService(db).summary(period=period)
