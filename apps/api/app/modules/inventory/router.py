import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.internal_auth import verify_internal_job_secret
from app.modules.auth.dependencies import RequireAdmin
from app.modules.inventory.models import MovementType
from app.modules.inventory.schemas import (
    AdjustmentRequest,
    ExpireReservationsResponse,
    InventoryCreate,
    InventoryListResponse,
    InventoryOperationResponse,
    InventoryRead,
    InventoryThresholdUpdate,
    LocationCreate,
    LocationListResponse,
    LocationRead,
    MovementListResponse,
    MovementRequest,
)
from app.modules.inventory.service import InventoryService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["inventory"])


@router.get("/admin/locations", response_model=LocationListResponse)
def list_locations(
    _admin: RequireAdmin,
    db: Annotated[Session, Depends(get_db)],
    q: str | None = Query(default=None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> LocationListResponse:
    return InventoryService(db).list_locations_paginated(
        q=q, page=page, page_size=page_size
    )


@router.post("/admin/locations", response_model=LocationRead, status_code=201)
def create_location(
    payload: LocationCreate,
    _admin: RequireAdmin,
    db: Annotated[Session, Depends(get_db)],
) -> LocationRead:
    return InventoryService(db).create_location(payload)


@router.get("/admin/inventory", response_model=InventoryListResponse)
def list_inventory(
    _admin: RequireAdmin,
    db: Annotated[Session, Depends(get_db)],
    location_id: UUID | None = None,
    product_id: UUID | None = None,
    q: str | None = Query(default=None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> InventoryListResponse:
    return InventoryService(db).list_inventory(
        location_id=location_id,
        product_id=product_id,
        q=q,
        page=page,
        page_size=page_size,
    )


@router.get("/admin/inventory/low-stock", response_model=list[InventoryRead])
def list_low_stock(
    _admin: RequireAdmin,
    db: Annotated[Session, Depends(get_db)],
    location_id: UUID | None = None,
) -> list[InventoryRead]:
    return InventoryService(db).list_low_stock(location_id=location_id)


@router.post("/admin/inventory", response_model=InventoryRead, status_code=201)
def create_inventory(
    payload: InventoryCreate,
    _admin: RequireAdmin,
    db: Annotated[Session, Depends(get_db)],
) -> InventoryRead:
    return InventoryService(db).create_inventory(payload)


@router.get("/admin/inventory/{product_id}", response_model=InventoryRead)
def get_inventory(
    product_id: UUID,
    _admin: RequireAdmin,
    db: Annotated[Session, Depends(get_db)],
    location_id: UUID | None = None,
) -> InventoryRead:
    return InventoryService(db).get_product_inventory(
        product_id, location_id=location_id
    )


@router.patch("/admin/inventory/{product_id}", response_model=InventoryRead)
def update_thresholds(
    product_id: UUID,
    payload: InventoryThresholdUpdate,
    _admin: RequireAdmin,
    db: Annotated[Session, Depends(get_db)],
    location_id: UUID | None = None,
) -> InventoryRead:
    return InventoryService(db).update_thresholds(
        product_id, payload, location_id=location_id
    )


@router.get(
    "/admin/inventory/{product_id}/movements",
    response_model=MovementListResponse,
)
def list_movements(
    product_id: UUID,
    _admin: RequireAdmin,
    db: Annotated[Session, Depends(get_db)],
    location_id: UUID | None = None,
    movement_type: MovementType | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> MovementListResponse:
    return InventoryService(db).list_movements(
        product_id,
        location_id=location_id,
        movement_type=movement_type,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/admin/inventory/{product_id}/purchase",
    response_model=InventoryOperationResponse,
)
def purchase(
    product_id: UUID,
    payload: MovementRequest,
    admin: RequireAdmin,
    db: Annotated[Session, Depends(get_db)],
) -> InventoryOperationResponse:
    return InventoryService(db).purchase(product_id, payload, admin)


@router.post(
    "/admin/inventory/{product_id}/sale",
    response_model=InventoryOperationResponse,
)
def sale(
    product_id: UUID,
    payload: MovementRequest,
    admin: RequireAdmin,
    db: Annotated[Session, Depends(get_db)],
) -> InventoryOperationResponse:
    """Prepared for future order flow; admin-only stock deduction."""
    return InventoryService(db).sale(product_id, payload, admin)


@router.post(
    "/admin/inventory/{product_id}/adjust",
    response_model=InventoryOperationResponse,
)
def adjust(
    product_id: UUID,
    payload: AdjustmentRequest,
    admin: RequireAdmin,
    db: Annotated[Session, Depends(get_db)],
) -> InventoryOperationResponse:
    return InventoryService(db).adjust(product_id, payload, admin)


@router.post(
    "/admin/inventory/{product_id}/reserve",
    response_model=InventoryOperationResponse,
)
def reserve(
    product_id: UUID,
    payload: MovementRequest,
    admin: RequireAdmin,
    db: Annotated[Session, Depends(get_db)],
) -> InventoryOperationResponse:
    return InventoryService(db).reserve(product_id, payload, admin)


@router.post(
    "/admin/inventory/{product_id}/release",
    response_model=InventoryOperationResponse,
)
def release(
    product_id: UUID,
    payload: MovementRequest,
    admin: RequireAdmin,
    db: Annotated[Session, Depends(get_db)],
) -> InventoryOperationResponse:
    return InventoryService(db).release(product_id, payload, admin)


@router.post(
    "/admin/inventory/{product_id}/return",
    response_model=InventoryOperationResponse,
)
def return_stock(
    product_id: UUID,
    payload: MovementRequest,
    admin: RequireAdmin,
    db: Annotated[Session, Depends(get_db)],
) -> InventoryOperationResponse:
    return InventoryService(db).return_stock(product_id, payload, admin)


@router.post(
    "/admin/inventory/{product_id}/damage",
    response_model=InventoryOperationResponse,
)
def damage(
    product_id: UUID,
    payload: MovementRequest,
    admin: RequireAdmin,
    db: Annotated[Session, Depends(get_db)],
) -> InventoryOperationResponse:
    return InventoryService(db).damage(product_id, payload, admin)


@router.post(
    "/internal/reservations/expire",
    response_model=ExpireReservationsResponse,
    tags=["internal"],
)
def expire_reservations(
    db: Annotated[Session, Depends(get_db)],
    x_gema_internal_secret: Annotated[str | None, Header()] = None,
) -> ExpireReservationsResponse:
    """Cron-ready job: release expired ACTIVE holds and cancel PENDING_PAYMENT orders."""
    verify_internal_job_secret(x_gema_internal_secret)
    try:
        result = InventoryService(db).expire_due_reservations(commit=True)
    except Exception:
        # Never log the internal secret header; message/traceback omit credentials.
        logger.exception("reservation expire job failed")
        raise
    logger.info(
        "reservation expire job ok expired=%s cancelled=%s",
        result["expired_reservations"],
        result["cancelled_orders"],
    )
    return ExpireReservationsResponse(**result)
