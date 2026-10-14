from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.auth.dependencies import CurrentUser
from app.modules.checkout.service import CheckoutService
from app.modules.orders.schemas import (
    CheckoutPreviewRequest,
    CheckoutPreviewResponse,
    CheckoutRequest,
    CheckoutResponse,
)

router = APIRouter(tags=["checkout"])


@router.post("/checkout/preview", response_model=CheckoutPreviewResponse)
def checkout_preview(
    payload: CheckoutPreviewRequest,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> CheckoutPreviewResponse:
    return CheckoutService(db).preview(user, payload)


@router.post("/checkout", response_model=CheckoutResponse)
def checkout(
    payload: CheckoutRequest,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> CheckoutResponse:
    return CheckoutService(db).checkout(user, payload)
