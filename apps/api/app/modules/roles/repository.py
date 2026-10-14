from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.roles.models import Role, UserRole
from app.modules.roles.schemas import DEFAULT_ROLES


class RoleRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_name(self, name: str) -> Role | None:
        return self.db.scalar(select(Role).where(Role.name == name))

    def list_all(self) -> list[Role]:
        return list(self.db.scalars(select(Role).order_by(Role.name)).all())

    def ensure_default_roles(self) -> list[Role]:
        roles: list[Role] = []
        for name, description in DEFAULT_ROLES:
            role = self.get_by_name(name)
            if role is None:
                role = Role(name=name, description=description)
                self.db.add(role)
                self.db.flush()
            roles.append(role)
        return roles

    def assign_role(self, user_id: UUID, role: Role) -> UserRole:
        existing = self.db.scalar(
            select(UserRole).where(UserRole.user_id == user_id, UserRole.role_id == role.id)
        )
        if existing is not None:
            return existing
        user_role = UserRole(user_id=user_id, role_id=role.id)
        self.db.add(user_role)
        self.db.flush()
        return user_role

    def remove_role_by_name(self, user_id: UUID, role_name: str) -> None:
        role = self.get_by_name(role_name)
        if role is None:
            return
        existing = self.db.scalar(
            select(UserRole).where(UserRole.user_id == user_id, UserRole.role_id == role.id)
        )
        if existing is not None:
            self.db.delete(existing)
            self.db.flush()
