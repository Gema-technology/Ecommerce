from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.auth.dependencies import CurrentUser
from app.modules.cart.schemas import CartItemCreate, CartItemUpdate, CartRead
from app.modules.cart.service import CartService

router = APIRouter(tags=["cart"])


def get_cart_service(db: Annotated[Session, Depends(get_db)]) -> CartService:
    return CartService(db)


@router.get("/cart", response_model=CartRead)
def get_cart(
    user: CurrentUser,
    service: Annotated[CartService, Depends(get_cart_service)],
) -> CartRead:
    return service.get_cart(user)


@router.post("/cart/items", response_model=CartRead)
def add_cart_item(
    payload: CartItemCreate,
    user: CurrentUser,
    service: Annotated[CartService, Depends(get_cart_service)],
) -> CartRead:
    return service.add_item(user, payload)


@router.patch("/cart/items/{item_id}", response_model=CartRead)
def update_cart_item(
    item_id: UUID,
    payload: CartItemUpdate,
    user: CurrentUser,
    service: Annotated[CartService, Depends(get_cart_service)],
) -> CartRead:
    return service.update_item(user, item_id, payload)


@router.delete("/cart/items/{item_id}", response_model=CartRead)
def remove_cart_item(
    item_id: UUID,
    user: CurrentUser,
    service: Annotated[CartService, Depends(get_cart_service)],
) -> CartRead:
    return service.remove_item(user, item_id)


@router.delete("/cart", response_model=CartRead)
def clear_cart(
    user: CurrentUser,
    service: Annotated[CartService, Depends(get_cart_service)],
) -> CartRead:
    return service.clear_cart(user)


@router.post("/cart/sync-prices", response_model=CartRead)
def sync_cart_prices(
    user: CurrentUser,
    service: Annotated[CartService, Depends(get_cart_service)],
) -> CartRead:
    """Acknowledge current effective prices and refresh cart quotes."""
    return service.sync_quoted_prices(user)
