"""Seed default roles and optional development admin user.

Usage:
  cd apps/api
  python -m app.scripts.seed

Optional env vars for a development admin (never hardcode passwords):
  SEED_ADMIN_EMAIL
  SEED_ADMIN_PASSWORD
"""

from datetime import UTC, datetime

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.modules.employees.models import Employee, EmployeeStatus
from app.modules.employees.repository import EmployeeRepository
from app.modules.roles.models import User
from app.modules.roles.repository import RoleRepository
from app.modules.roles.schemas import ROLE_SUPER_ADMIN
from app.modules.users.repository import UserRepository
from app.modules.users.schemas import normalize_email


def seed() -> None:
    db = SessionLocal()
    try:
        roles = RoleRepository(db)
        users = UserRepository(db)
        employees = EmployeeRepository(db)

        roles.ensure_default_roles()
        print("Roles seeded: CUSTOMER, ADMIN, SUPER_ADMIN")

        if settings.seed_admin_email and settings.seed_admin_password:
            email = normalize_email(settings.seed_admin_email)
            existing = users.get_by_email(email)
            if existing is None:
                admin = User(
                    email=email,
                    password_hash=hash_password(settings.seed_admin_password),
                    first_name="Admin",
                    last_name="GEMA",
                    is_active=True,
                    email_verified=True,
                )
                users.create(admin)
                super_role = roles.get_by_name(ROLE_SUPER_ADMIN)
                assert super_role is not None
                roles.assign_role(admin.id, super_role)
                employees.create(
                    Employee(
                        user_id=admin.id,
                        status=EmployeeStatus.ACTIVE.value,
                        accepted_at=datetime.now(UTC),
                    )
                )
                print(f"Development admin created: {email}")
            else:
                if employees.get_by_user_id(existing.id) is None:
                    employees.create(
                        Employee(
                            user_id=existing.id,
                            status=EmployeeStatus.ACTIVE.value,
                            accepted_at=datetime.now(UTC),
                        )
                    )
                    print(f"Employee profile linked for existing admin: {email}")
                print(f"Admin already exists: {email}")
        else:
            print("No SEED_ADMIN_EMAIL/SEED_ADMIN_PASSWORD set; skipping admin user.")

        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    seed()
