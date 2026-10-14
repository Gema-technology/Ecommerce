from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.pagination import offset_for
from app.modules.employees.models import Employee
from app.modules.roles.models import User, UserRole


class EmployeeRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, employee_id: UUID) -> Employee | None:
        return self.db.scalar(
            select(Employee)
            .where(Employee.id == employee_id)
            .options(
                selectinload(Employee.user).selectinload(User.user_roles).selectinload(UserRole.role)
            )
        )

    def get_by_user_id(self, user_id: UUID) -> Employee | None:
        return self.db.scalar(select(Employee).where(Employee.user_id == user_id))

    def get_by_invite_token_hash(self, token_hash: str) -> Employee | None:
        return self.db.scalar(
            select(Employee)
            .where(Employee.invite_token_hash == token_hash)
            .options(
                selectinload(Employee.user).selectinload(User.user_roles).selectinload(UserRole.role)
            )
        )

    def list_employees(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        q: str | None = None,
        status: str | None = None,
    ) -> tuple[list[Employee], int]:
        filters = []
        if status:
            filters.append(Employee.status == status)
        if q:
            term = f"%{q.strip()}%"
            filters.append(
                or_(
                    User.email.ilike(term),
                    User.first_name.ilike(term),
                    User.last_name.ilike(term),
                    Employee.job_title.ilike(term),
                )
            )

        count_stmt = select(func.count()).select_from(Employee).join(User, User.id == Employee.user_id)
        stmt = (
            select(Employee)
            .join(User, User.id == Employee.user_id)
            .options(
                selectinload(Employee.user)
                .selectinload(User.user_roles)
                .selectinload(UserRole.role)
            )
            .order_by(Employee.created_at.desc())
        )
        for f in filters:
            count_stmt = count_stmt.where(f)
            stmt = stmt.where(f)
        total = int(self.db.scalar(count_stmt) or 0)
        items = list(
            self.db.scalars(
                stmt.offset(offset_for(page, page_size)).limit(page_size)
            )
            .unique()
            .all()
        )
        return items, total

    def count_super_admins(self, *, exclude_user_id: UUID | None = None) -> int:
        from app.modules.roles.models import Role
        from app.modules.roles.schemas import ROLE_SUPER_ADMIN

        stmt = (
            select(func.count())
            .select_from(UserRole)
            .join(Role, Role.id == UserRole.role_id)
            .where(Role.name == ROLE_SUPER_ADMIN)
        )
        if exclude_user_id is not None:
            stmt = stmt.where(UserRole.user_id != exclude_user_id)
        return int(self.db.scalar(stmt) or 0)

    def create(self, employee: Employee) -> Employee:
        self.db.add(employee)
        self.db.flush()
        return employee

    def save(self, employee: Employee) -> Employee:
        self.db.add(employee)
        self.db.flush()
        return employee
