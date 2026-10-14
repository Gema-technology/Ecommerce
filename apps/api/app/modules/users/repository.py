from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.pagination import offset_for
from app.modules.employees.models import Employee
from app.modules.roles.models import User, UserRole


def _user_with_roles():
    return selectinload(User.user_roles).selectinload(UserRole.role)


class UserRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, user_id: UUID) -> User | None:
        return self.db.scalar(select(User).where(User.id == user_id).options(_user_with_roles()))

    def get_by_email(self, email: str) -> User | None:
        return self.db.scalar(select(User).where(User.email == email).options(_user_with_roles()))

    def create(self, user: User) -> User:
        self.db.add(user)
        self.db.flush()
        return user

    def list_users(self, *, offset: int = 0, limit: int = 50) -> list[User]:
        stmt = (
            select(User)
            .options(_user_with_roles())
            .order_by(User.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(self.db.scalars(stmt).all())

    def list_customers(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        q: str | None = None,
        is_active: bool | None = None,
    ) -> tuple[list[User], int]:
        """Storefront customers: users without an employees row."""
        employee_user_ids = select(Employee.user_id)
        filters = [~User.id.in_(employee_user_ids)]
        if is_active is True:
            filters.append(User.is_active.is_(True))
        elif is_active is False:
            filters.append(User.is_active.is_(False))
        if q:
            term = f"%{q.strip()}%"
            filters.append(
                or_(
                    User.email.ilike(term),
                    User.first_name.ilike(term),
                    User.last_name.ilike(term),
                )
            )
        count_stmt = select(func.count()).select_from(User)
        stmt = (
            select(User)
            .options(_user_with_roles())
            .order_by(User.created_at.desc())
        )
        for f in filters:
            count_stmt = count_stmt.where(f)
            stmt = stmt.where(f)
        total = int(self.db.scalar(count_stmt) or 0)
        items = list(
            self.db.scalars(
                stmt.offset(offset_for(page, page_size)).limit(page_size)
            ).all()
        )
        return items, total

    def save(self, user: User) -> User:
        self.db.add(user)
        self.db.flush()
        return user
