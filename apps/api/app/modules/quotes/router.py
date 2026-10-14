from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.auth.dependencies import RequireAdmin
from app.modules.quotes.pdf import generate_quote_pdf
from app.modules.quotes.schemas import (
    PricingConfigRead,
    PricingConfigUpdate,
    QuoteCreate,
    QuoteListResponse,
    QuoteProductCreate,
    QuoteProductListResponse,
    QuoteProductRead,
    QuoteProductUpdate,
    QuoteRead,
    QuoteUpdate,
)
from app.modules.quotes.service import QuoteService
from app.modules.store_config.service import StoreConfigService

router = APIRouter(tags=["quotes"])


def get_quote_service(db: Annotated[Session, Depends(get_db)]) -> QuoteService:
    return QuoteService(db)


@router.get("/admin/pricing-config", response_model=PricingConfigRead)
def get_pricing_config(
    _admin: RequireAdmin,
    service: Annotated[QuoteService, Depends(get_quote_service)],
) -> PricingConfigRead:
    return service.get_pricing_config()


@router.put("/admin/pricing-config", response_model=PricingConfigRead)
def update_pricing_config(
    payload: PricingConfigUpdate,
    _admin: RequireAdmin,
    service: Annotated[QuoteService, Depends(get_quote_service)],
) -> PricingConfigRead:
    return service.update_pricing_config(payload)


@router.get("/admin/catalog/products", response_model=QuoteProductListResponse)
def list_catalog_products(
    _admin: RequireAdmin,
    service: Annotated[QuoteService, Depends(get_quote_service)],
    q: str | None = Query(default=None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    active_only: bool = Query(False),
) -> QuoteProductListResponse:
    return service.list_products(q=q, page=page, page_size=page_size, active_only=active_only)


@router.post("/admin/catalog/products", response_model=QuoteProductRead, status_code=201)
def create_catalog_product(
    payload: QuoteProductCreate,
    _admin: RequireAdmin,
    service: Annotated[QuoteService, Depends(get_quote_service)],
) -> QuoteProductRead:
    return service.create_product(payload)


@router.put("/admin/catalog/products/{product_id}", response_model=QuoteProductRead)
def update_catalog_product(
    product_id: UUID,
    payload: QuoteProductUpdate,
    _admin: RequireAdmin,
    service: Annotated[QuoteService, Depends(get_quote_service)],
) -> QuoteProductRead:
    return service.update_product(product_id, payload)


@router.delete("/admin/catalog/products/{product_id}", status_code=204)
def delete_catalog_product(
    product_id: UUID,
    _admin: RequireAdmin,
    service: Annotated[QuoteService, Depends(get_quote_service)],
) -> None:
    service.delete_product(product_id)


@router.get("/admin/quotes", response_model=QuoteListResponse)
def list_quotes(
    _admin: RequireAdmin,
    service: Annotated[QuoteService, Depends(get_quote_service)],
    status: str | None = Query(default=None),
    client: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> QuoteListResponse:
    return service.list_quotes(
        status=status,
        client=client,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )


@router.post("/admin/quotes", response_model=QuoteRead, status_code=201)
def create_quote(
    payload: QuoteCreate,
    admin: RequireAdmin,
    service: Annotated[QuoteService, Depends(get_quote_service)],
) -> QuoteRead:
    return service.create_quote(payload, admin)


@router.get("/admin/quotes/{quote_id}", response_model=QuoteRead)
def get_quote(
    quote_id: UUID,
    _admin: RequireAdmin,
    service: Annotated[QuoteService, Depends(get_quote_service)],
) -> QuoteRead:
    return service.get_quote(quote_id)


@router.put("/admin/quotes/{quote_id}", response_model=QuoteRead)
def update_quote(
    quote_id: UUID,
    payload: QuoteUpdate,
    _admin: RequireAdmin,
    service: Annotated[QuoteService, Depends(get_quote_service)],
) -> QuoteRead:
    return service.update_quote(quote_id, payload)


@router.delete("/admin/quotes/{quote_id}", status_code=204)
def delete_quote(
    quote_id: UUID,
    _admin: RequireAdmin,
    service: Annotated[QuoteService, Depends(get_quote_service)],
) -> None:
    service.delete_quote(quote_id)


@router.get("/admin/quotes/{quote_id}/pdf")
def download_quote_pdf(
    quote_id: UUID,
    _admin: RequireAdmin,
    service: Annotated[QuoteService, Depends(get_quote_service)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    quote = service.get_quote_entity(quote_id)
    store_config = StoreConfigService(db).get_read()
    pdf_bytes = generate_quote_pdf(quote, store_config=store_config)
    filename = f"{quote.number}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
