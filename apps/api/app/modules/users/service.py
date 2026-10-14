from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.employees.models import Employee
from app.modules.roles.models import User
from app.modules.users.repository import UserRepository
from app.modules.users.schemas import (
    AdminUserCodUpdate,
    CustomerActiveUpdate,
    CustomerListItem,
    CustomerListResponse,
    UserProfileUpdate,
    UserPublic,
)


def user_to_public(user: User) -> UserPublic:
    return UserPublic(
        id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        phone=user.phone,
        is_active=user.is_active,
        email_verified=user.email_verified,
        allow_cash_on_delivery=bool(user.allow_cash_on_delivery),
        roles=user.role_names,
    )


def _to_customer_item(user: User) -> CustomerListItem:
    return CustomerListItem(
        id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        is_active=user.is_active,
        allow_cash_on_delivery=bool(user.allow_cash_on_delivery),
        roles=user.role_names,
    )


class UserService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.users = UserRepository(db)

    def get_profile(self, user_id: UUID) -> UserPublic:
        user = self.users.get_by_id(user_id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        return user_to_public(user)

    def update_profile(self, user_id: UUID, data: UserProfileUpdate) -> UserPublic:
        user = self.users.get_by_id(user_id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        updates = data.model_dump(exclude_unset=True)
        for field, value in updates.items():
            setattr(user, field, value)

        self.users.save(user)
        self.db.commit()
        self.db.refresh(user)
        user = self.users.get_by_id(user.id)
        assert user is not None
        return user_to_public(user)

    def _require_customer(self, user_id: UUID) -> User:
        user = self.users.get_by_id(user_id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
        emp = self.db.scalar(select(Employee.id).where(Employee.user_id == user_id))
        if emp is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User is an employee; manage them under Equipo",
            )
        return user

    def list_customers_for_admin(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        q: str | None = None,
        is_active: bool | None = None,
    ) -> CustomerListResponse:
        from app.core.pagination import total_pages

        items, total = self.users.list_customers(
            page=page,
            page_size=page_size,
            q=q,
            is_active=is_active,
        )
        return CustomerListResponse(
            items=[_to_customer_item(u) for u in items],
            page=page,
            page_size=page_size,
            total=total,
            total_pages=total_pages(total, page_size),
        )

    def set_cash_on_delivery_allowed(
        self, user_id: UUID, data: AdminUserCodUpdate
    ) -> CustomerListItem:
        user = self._require_customer(user_id)
        user.allow_cash_on_delivery = data.allow_cash_on_delivery
        self.users.save(user)
        self.db.commit()
        user = self.users.get_by_id(user.id)
        assert user is not None
        return _to_customer_item(user)

    def set_customer_active(self, user_id: UUID, data: CustomerActiveUpdate) -> CustomerListItem:
        user = self._require_customer(user_id)
        user.is_active = data.is_active
        self.users.save(user)
        self.db.commit()
        user = self.users.get_by_id(user.id)
        assert user is not None
        return _to_customer_item(user)
