from typing import Annotated
from uuid import UUID
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.auth.dependencies import RequireAdmin
from app.modules.products.schemas import (
    ProductCreate,
    ProductListResponse,
    ProductRead,
    ProductSort,
    ProductUpdate,
)
from app.modules.products.service import ProductService

router = APIRouter(tags=["products"])


@router.get("/products", response_model=ProductListResponse)
def list_products(
    db: Annotated[Session, Depends(get_db)],
    category: str | None = None,
    brand: str | None = None,
    search: str | None = None,
    sort: ProductSort = ProductSort.NEWEST,
    min_price: Decimal | None = Query(default=None, ge=0),
    max_price: Decimal | None = Query(default=None, ge=0),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> ProductListResponse:
    return ProductService(db).list_products(
        category=category,
        brand=brand,
        is_active=True,
        min_price=min_price,
        max_price=max_price,
        search=search,
        sort=sort,
        page=page,
        page_size=page_size,
    )


@router.get("/products/{slug}", response_model=ProductRead)
def get_product(slug: str, db: Annotated[Session, Depends(get_db)]) -> ProductRead:
    return ProductService(db).get_by_slug(slug)


@router.post("/admin/products", response_model=ProductRead, status_code=201)
def create_product(
    payload: ProductCreate,
    _admin: RequireAdmin,
    db: Annotated[Session, Depends(get_db)],
) -> ProductRead:
    return ProductService(db).create(payload)


@router.patch("/admin/products/{product_id}", response_model=ProductRead)
def update_product(
    product_id: UUID,
    payload: ProductUpdate,
    _admin: RequireAdmin,
    db: Annotated[Session, Depends(get_db)],
) -> ProductRead:
    return ProductService(db).update(product_id, payload)


@router.delete("/admin/products/{product_id}", response_model=ProductRead)
def delete_product(
    product_id: UUID,
    _admin: RequireAdmin,
    db: Annotated[Session, Depends(get_db)],
) -> ProductRead:
    return ProductService(db).soft_delete(product_id)


@router.get("/admin/products", response_model=ProductListResponse)
def list_products_admin(
    _admin: RequireAdmin,
    db: Annotated[Session, Depends(get_db)],
    category: str | None = None,
    brand: str | None = None,
    search: str | None = None,
    sort: ProductSort = ProductSort.NEWEST,
    is_active: bool | None = None,
    min_price: Decimal | None = Query(default=None, ge=0),
    max_price: Decimal | None = Query(default=None, ge=0),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> ProductListResponse:
    return ProductService(db).list_products(
        category=category,
        brand=brand,
        is_active=is_active,
        min_price=min_price,
        max_price=max_price,
        search=search,
        sort=sort,
        page=page,
        page_size=page_size,
    )
