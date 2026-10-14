from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.auth.dependencies import CurrentUser, RequireAdmin
from app.modules.users.schemas import (
    AdminUserCodUpdate,
    CustomerActiveUpdate,
    CustomerListItem,
    CustomerListResponse,
    UserProfileUpdate,
    UserPublic,
)
from app.modules.users.service import UserService

router = APIRouter(tags=["users"])


@router.get("/users/me", response_model=UserPublic)
def get_my_profile(user: CurrentUser, db: Annotated[Session, Depends(get_db)]) -> UserPublic:
    return UserService(db).get_profile(user.id)


@router.patch("/users/me", response_model=UserPublic)
def update_my_profile(
    payload: UserProfileUpdate,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> UserPublic:
    return UserService(db).update_profile(user.id, payload)


@router.get("/admin/customers", response_model=CustomerListResponse)
def list_customers_admin(
    _admin: RequireAdmin,
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    q: str | None = Query(default=None),
    is_active: bool | None = Query(default=None),
) -> CustomerListResponse:
    return UserService(db).list_customers_for_admin(
        page=page,
        page_size=page_size,
        q=q,
        is_active=is_active,
    )


@router.patch("/admin/customers/{user_id}/cash-on-delivery", response_model=CustomerListItem)
def set_customer_cash_on_delivery(
    user_id: UUID,
    payload: AdminUserCodUpdate,
    _admin: RequireAdmin,
    db: Annotated[Session, Depends(get_db)],
) -> CustomerListItem:
    """Whitelist a customer for cash-on-delivery (trusted buyers only)."""
    return UserService(db).set_cash_on_delivery_allowed(user_id, payload)


@router.patch("/admin/customers/{user_id}/active", response_model=CustomerListItem)
def set_customer_active(
    user_id: UUID,
    payload: CustomerActiveUpdate,
    _admin: RequireAdmin,
    db: Annotated[Session, Depends(get_db)],
) -> CustomerListItem:
    return UserService(db).set_customer_active(user_id, payload)
