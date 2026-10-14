from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.auth.dependencies import RequireAdmin
from app.modules.suppliers.schemas import (
    ProductSupplierLinkCreate,
    ProductSuppliersResponse,
    SupplierCreate,
    SupplierListResponse,
    SupplierProductCreate,
    SupplierProductRead,
    SupplierProductUpdate,
    SupplierRead,
    SupplierUpdate,
)
from app.modules.suppliers.service import SupplierService

router = APIRouter(tags=["suppliers"])


@router.get("/admin/suppliers", response_model=SupplierListResponse)
def list_suppliers(
    _admin: RequireAdmin,
    db: Annotated[Session, Depends(get_db)],
    search: str | None = None,
    is_active: bool | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> SupplierListResponse:
    return SupplierService(db).list_suppliers(
        active_only=is_active,
        search=search,
        page=page,
        page_size=page_size,
    )


@router.post("/admin/suppliers", response_model=SupplierRead, status_code=201)
def create_supplier(
    payload: SupplierCreate,
    _admin: RequireAdmin,
    db: Annotated[Session, Depends(get_db)],
) -> SupplierRead:
    return SupplierService(db).create(payload)


@router.get("/admin/suppliers/{supplier_id}", response_model=SupplierRead)
def get_supplier(
    supplier_id: UUID,
    _admin: RequireAdmin,
    db: Annotated[Session, Depends(get_db)],
) -> SupplierRead:
    return SupplierService(db).get_by_id(supplier_id)


@router.patch("/admin/suppliers/{supplier_id}", response_model=SupplierRead)
def update_supplier(
    supplier_id: UUID,
    payload: SupplierUpdate,
    _admin: RequireAdmin,
    db: Annotated[Session, Depends(get_db)],
) -> SupplierRead:
    return SupplierService(db).update(supplier_id, payload)


@router.delete("/admin/suppliers/{supplier_id}", response_model=SupplierRead)
def delete_supplier(
    supplier_id: UUID,
    _admin: RequireAdmin,
    db: Annotated[Session, Depends(get_db)],
) -> SupplierRead:
    return SupplierService(db).soft_delete(supplier_id)


@router.get(
    "/admin/suppliers/{supplier_id}/products",
    response_model=list[SupplierProductRead],
)
def list_supplier_products(
    supplier_id: UUID,
    _admin: RequireAdmin,
    db: Annotated[Session, Depends(get_db)],
    is_active: bool | None = Query(default=None),
) -> list[SupplierProductRead]:
    return SupplierService(db).list_supplier_products(supplier_id, active_only=is_active)


@router.post(
    "/admin/suppliers/{supplier_id}/products",
    response_model=SupplierProductRead,
    status_code=201,
)
def create_supplier_product(
    supplier_id: UUID,
    payload: SupplierProductCreate,
    _admin: RequireAdmin,
    db: Annotated[Session, Depends(get_db)],
) -> SupplierProductRead:
    return SupplierService(db).create_supplier_product(supplier_id, payload)


@router.patch(
    "/admin/suppliers/{supplier_id}/products/{supplier_product_id}",
    response_model=SupplierProductRead,
)
def update_supplier_product(
    supplier_id: UUID,
    supplier_product_id: UUID,
    payload: SupplierProductUpdate,
    _admin: RequireAdmin,
    db: Annotated[Session, Depends(get_db)],
) -> SupplierProductRead:
    return SupplierService(db).update_supplier_product(
        supplier_id, supplier_product_id, payload
    )


@router.delete(
    "/admin/suppliers/{supplier_id}/products/{supplier_product_id}",
    response_model=SupplierProductRead,
)
def delete_supplier_product(
    supplier_id: UUID,
    supplier_product_id: UUID,
    _admin: RequireAdmin,
    db: Annotated[Session, Depends(get_db)],
) -> SupplierProductRead:
    return SupplierService(db).soft_delete_supplier_product(supplier_id, supplier_product_id)


@router.get(
    "/admin/products/{product_id}/suppliers",
    response_model=ProductSuppliersResponse,
)
def list_product_suppliers(
    product_id: UUID,
    _admin: RequireAdmin,
    db: Annotated[Session, Depends(get_db)],
) -> ProductSuppliersResponse:
    return SupplierService(db).list_product_suppliers(product_id)


@router.post(
    "/admin/products/{product_id}/suppliers",
    response_model=SupplierProductRead,
    status_code=201,
)
def link_product_supplier(
    product_id: UUID,
    payload: ProductSupplierLinkCreate,
    _admin: RequireAdmin,
    db: Annotated[Session, Depends(get_db)],
) -> SupplierProductRead:
    return SupplierService(db).link_product_supplier(product_id, payload)
