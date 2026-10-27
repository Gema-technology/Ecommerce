import secrets
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.modules.employees.models import Employee
from app.modules.orders.models import Order
from app.modules.roles.models import User
from app.modules.roles.repository import RoleRepository
from app.modules.roles.schemas import ROLE_CUSTOMER
from app.modules.users.repository import UserRepository
from app.modules.users.schemas import (
    AdminUserCodUpdate,
    CustomerActiveUpdate,
    CustomerCreate,
    CustomerListItem,
    CustomerListResponse,
    CustomerUpdate,
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
        phone=user.phone,
        tax_id_type=user.tax_id_type,
        tax_id=user.tax_id,
        address_line=user.address_line,
        address_reference=user.address_reference,
        city=user.city,
        province=user.province,
        country=user.country or "Ecuador",
        postal_code=user.postal_code,
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

    def get_customer(self, user_id: UUID) -> CustomerListItem:
        return _to_customer_item(self._require_customer(user_id))

    def create_customer(self, data: CustomerCreate) -> CustomerListItem:
        if self.users.get_by_email(data.email) is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered",
            )
        roles = RoleRepository(self.db)
        customer_role = roles.get_by_name(ROLE_CUSTOMER)
        if customer_role is None:
            roles.ensure_default_roles()
            customer_role = roles.get_by_name(ROLE_CUSTOMER)
        if customer_role is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Default roles are not seeded",
            )
        user = User(
            email=data.email,
            password_hash=hash_password(data.password or secrets.token_urlsafe(32)),
            first_name=data.first_name,
            last_name=data.last_name,
            phone=data.phone,
            tax_id_type=data.tax_id_type,
            tax_id=data.tax_id,
            address_line=data.address_line,
            address_reference=data.address_reference,
            city=data.city,
            province=data.province,
            country=data.country,
            postal_code=data.postal_code,
            is_active=True,
            email_verified=False,
        )
        self.users.create(user)
        roles.assign_role(user.id, customer_role)
        self.db.commit()
        created = self.users.get_by_id(user.id)
        assert created is not None
        return _to_customer_item(created)

    def update_customer(self, user_id: UUID, data: CustomerUpdate) -> CustomerListItem:
        user = self._require_customer(user_id)
        updates = data.model_dump(exclude_unset=True)
        if "email" in updates and updates["email"] != user.email:
            taken = self.users.get_by_email(updates["email"])
            if taken is not None and taken.id != user.id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Email already registered",
                )
            user.email = updates["email"]
        if "password" in updates and updates["password"]:
            user.password_hash = hash_password(updates["password"])
        for field in (
            "first_name",
            "last_name",
            "phone",
            "tax_id_type",
            "tax_id",
            "address_line",
            "address_reference",
            "city",
            "province",
            "country",
            "postal_code",
        ):
            if field in updates:
                setattr(user, field, updates[field])
        self.users.save(user)
        self.db.commit()
        updated = self.users.get_by_id(user.id)
        assert updated is not None
        return _to_customer_item(updated)

    def delete_customer(self, user_id: UUID) -> None:
        user = self._require_customer(user_id)
        order_count = self.db.scalar(
            select(func.count()).select_from(Order).where(Order.user_id == user.id)
        )
        if order_count:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="El cliente tiene pedidos. Desactívalo en lugar de eliminarlo.",
            )
        self.db.delete(user)
        self.db.commit()

    def set_customer_active(self, user_id: UUID, data: CustomerActiveUpdate) -> CustomerListItem:
        user = self._require_customer(user_id)
        user.is_active = data.is_active
        self.users.save(user)
        self.db.commit()
        user = self.users.get_by_id(user.id)
        assert user is not None
        return _to_customer_item(user)
