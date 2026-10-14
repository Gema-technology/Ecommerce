from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.auth.dependencies import RequireAdmin
from app.modules.pricing.models import PriceType
from app.modules.pricing.schemas import (
    MarginResult,
    ProductPriceCreate,
    ProductPriceRead,
    ProductPriceUpdate,
)
from app.modules.pricing.service import PricingService, calculate_margin
from app.modules.pricing.schemas import MarginRequest

router = APIRouter(tags=["pricing"])


@router.post(
    "/admin/products/{product_id}/prices",
    response_model=ProductPriceRead,
    status_code=201,
)
def create_price(
    product_id: UUID,
    payload: ProductPriceCreate,
    admin: RequireAdmin,
    db: Annotated[Session, Depends(get_db)],
) -> ProductPriceRead:
    return PricingService(db).create_price(product_id, payload, admin)


@router.get(
    "/admin/products/{product_id}/prices",
    response_model=list[ProductPriceRead],
)
def list_prices(
    product_id: UUID,
    _admin: RequireAdmin,
    db: Annotated[Session, Depends(get_db)],
    price_type: PriceType | None = None,
    is_active: bool | None = None,
) -> list[ProductPriceRead]:
    return PricingService(db).list_prices(
        product_id, price_type=price_type, active_only=is_active
    )


@router.get(
    "/admin/products/{product_id}/prices/current",
    response_model=ProductPriceRead | None,
)
def get_current_price(
    product_id: UUID,
    _admin: RequireAdmin,
    db: Annotated[Session, Depends(get_db)],
    price_type: PriceType = PriceType.RETAIL,
) -> ProductPriceRead | None:
    return PricingService(db).get_current_price(product_id, price_type=price_type)


@router.get(
    "/admin/products/{product_id}/prices/history",
    response_model=list[ProductPriceRead],
)
def get_price_history(
    product_id: UUID,
    _admin: RequireAdmin,
    db: Annotated[Session, Depends(get_db)],
) -> list[ProductPriceRead]:
    return PricingService(db).get_price_history(product_id)


@router.patch(
    "/admin/products/{product_id}/prices/{price_id}",
    response_model=ProductPriceRead,
)
def update_price(
    product_id: UUID,
    price_id: UUID,
    payload: ProductPriceUpdate,
    _admin: RequireAdmin,
    db: Annotated[Session, Depends(get_db)],
) -> ProductPriceRead:
    return PricingService(db).update_price(product_id, price_id, payload)


@router.delete(
    "/admin/products/{product_id}/prices/{price_id}",
    response_model=ProductPriceRead,
)
def deactivate_price(
    product_id: UUID,
    price_id: UUID,
    _admin: RequireAdmin,
    db: Annotated[Session, Depends(get_db)],
) -> ProductPriceRead:
    return PricingService(db).deactivate_price(product_id, price_id)


@router.get(
    "/admin/products/{product_id}/margin",
    response_model=MarginResult,
)
def get_margin(
    product_id: UUID,
    _admin: RequireAdmin,
    db: Annotated[Session, Depends(get_db)],
    supplier_product_id: UUID | None = None,
    price_type: PriceType = PriceType.RETAIL,
) -> MarginResult:
    return PricingService(db).calculate_margin_for_product(
        product_id,
        supplier_product_id=supplier_product_id,
        price_type=price_type,
    )


@router.post("/admin/pricing/margin", response_model=MarginResult)
def compute_margin(
    payload: MarginRequest,
    _admin: RequireAdmin,
) -> MarginResult:
    return calculate_margin(
        payload.sale_price, payload.cost, cost_source=payload.cost_source
    )
