from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.auth.dependencies import CurrentUser, RequireAdmin
from app.modules.orders.schemas import (
    CounterSaleRequest,
    OrderListResponse,
    OrderRead,
    OrderStatusUpdateRequest,
)
from app.modules.orders.service import OrderService

router = APIRouter(tags=["orders"])


def get_order_service(db: Annotated[Session, Depends(get_db)]) -> OrderService:
    return OrderService(db)


@router.get("/orders", response_model=OrderListResponse)
def list_my_orders(
    user: CurrentUser,
    service: Annotated[OrderService, Depends(get_order_service)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> OrderListResponse:
    return service.list_for_user(user, page=page, page_size=page_size)


@router.get("/orders/by-number/{order_number}", response_model=OrderRead)
def get_my_order_by_number(
    order_number: str,
    user: CurrentUser,
    service: Annotated[OrderService, Depends(get_order_service)],
) -> OrderRead:
    return service.get_by_number_for_user(user, order_number)


@router.post("/orders/{order_id}/cancel", response_model=OrderRead)
def cancel_my_order(
    order_id: UUID,
    user: CurrentUser,
    service: Annotated[OrderService, Depends(get_order_service)],
) -> OrderRead:
    return service.cancel_for_user(user, order_id)


@router.get("/orders/{order_id}", response_model=OrderRead)
def get_my_order(
    order_id: UUID,
    user: CurrentUser,
    service: Annotated[OrderService, Depends(get_order_service)],
) -> OrderRead:
    return service.get_for_user(user, order_id)


@router.post("/admin/orders/counter-sale", response_model=OrderRead, status_code=201)
def admin_counter_sale(
    payload: CounterSaleRequest,
    admin: RequireAdmin,
    service: Annotated[OrderService, Depends(get_order_service)],
) -> OrderRead:
    return service.create_counter_sale(admin, payload)


@router.get("/admin/orders", response_model=OrderListResponse)
def admin_list_orders(
    _admin: RequireAdmin,
    service: Annotated[OrderService, Depends(get_order_service)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = Query(default=None),
) -> OrderListResponse:
    return service.admin_list(page=page, page_size=page_size, status=status)


@router.post("/admin/orders/{order_id}/cancel", response_model=OrderRead)
def admin_cancel_order(
    order_id: UUID,
    admin: RequireAdmin,
    service: Annotated[OrderService, Depends(get_order_service)],
) -> OrderRead:
    return service.admin_cancel(order_id, admin)


@router.patch("/admin/orders/{order_id}/status", response_model=OrderRead)
def admin_update_order_status(
    order_id: UUID,
    payload: OrderStatusUpdateRequest,
    admin: RequireAdmin,
    service: Annotated[OrderService, Depends(get_order_service)],
) -> OrderRead:
    """Admin fulfillment: PAID→PROCESSING→SHIPPED→DELIVERED only."""
    return service.admin_update_status(order_id, admin, payload)


@router.get("/admin/orders/{order_id}", response_model=OrderRead)
def admin_get_order(
    order_id: UUID,
    _admin: RequireAdmin,
    service: Annotated[OrderService, Depends(get_order_service)],
) -> OrderRead:
    return service.admin_get(order_id)
