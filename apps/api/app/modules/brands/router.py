from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.auth.dependencies import RequireAdmin
from app.modules.brands.schemas import BrandCreate, BrandListResponse, BrandRead, BrandUpdate
from app.modules.brands.service import BrandService

router = APIRouter(tags=["brands"])


@router.get("/brands", response_model=list[BrandRead])
def list_brands(
    db: Annotated[Session, Depends(get_db)],
    category: str | None = None,
) -> list[BrandRead]:
    return BrandService(db).list_brands(active_only=True, category_slug=category)


@router.get("/admin/brands", response_model=BrandListResponse)
def list_brands_admin(
    _admin: RequireAdmin,
    db: Annotated[Session, Depends(get_db)],
    category: str | None = None,
    q: str | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> BrandListResponse:
    return BrandService(db).list_brands_paginated(
        category_slug=category,
        q=q,
        is_active=is_active,
        page=page,
        page_size=page_size,
    )


@router.get("/brands/{slug}", response_model=BrandRead)
def get_brand(slug: str, db: Annotated[Session, Depends(get_db)]) -> BrandRead:
    return BrandService(db).get_by_slug(slug)


@router.post("/admin/brands", response_model=BrandRead, status_code=201)
def create_brand(
    payload: BrandCreate,
    _admin: RequireAdmin,
    db: Annotated[Session, Depends(get_db)],
) -> BrandRead:
    return BrandService(db).create(payload)


@router.patch("/admin/brands/{brand_id}", response_model=BrandRead)
def update_brand(
    brand_id: UUID,
    payload: BrandUpdate,
    _admin: RequireAdmin,
    db: Annotated[Session, Depends(get_db)],
) -> BrandRead:
    return BrandService(db).update(brand_id, payload)


@router.delete("/admin/brands/{brand_id}", response_model=BrandRead)
def delete_brand(
    brand_id: UUID,
    _admin: RequireAdmin,
    db: Annotated[Session, Depends(get_db)],
) -> BrandRead:
    return BrandService(db).soft_delete(brand_id)
