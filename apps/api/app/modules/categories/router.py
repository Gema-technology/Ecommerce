from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.auth.dependencies import RequireAdmin
from app.modules.categories.schemas import CategoryCreate, CategoryRead, CategoryUpdate
from app.modules.categories.service import CategoryService

router = APIRouter(tags=["categories"])


@router.get("/categories", response_model=list[CategoryRead])
def list_categories(db: Annotated[Session, Depends(get_db)]) -> list[CategoryRead]:
    return CategoryService(db).list_categories(active_only=True)


@router.get("/admin/categories", response_model=list[CategoryRead])
def list_categories_admin(
    _admin: RequireAdmin,
    db: Annotated[Session, Depends(get_db)],
) -> list[CategoryRead]:
    return CategoryService(db).list_categories(active_only=False)


@router.get("/categories/{slug}", response_model=CategoryRead)
def get_category(slug: str, db: Annotated[Session, Depends(get_db)]) -> CategoryRead:
    return CategoryService(db).get_by_slug(slug)


@router.post("/admin/categories", response_model=CategoryRead, status_code=201)
def create_category(
    payload: CategoryCreate,
    _admin: RequireAdmin,
    db: Annotated[Session, Depends(get_db)],
) -> CategoryRead:
    return CategoryService(db).create(payload)


@router.patch("/admin/categories/{category_id}", response_model=CategoryRead)
def update_category(
    category_id: UUID,
    payload: CategoryUpdate,
    _admin: RequireAdmin,
    db: Annotated[Session, Depends(get_db)],
) -> CategoryRead:
    return CategoryService(db).update(category_id, payload)


@router.delete("/admin/categories/{category_id}", response_model=CategoryRead)
def delete_category(
    category_id: UUID,
    _admin: RequireAdmin,
    db: Annotated[Session, Depends(get_db)],
) -> CategoryRead:
    return CategoryService(db).soft_delete(category_id)
