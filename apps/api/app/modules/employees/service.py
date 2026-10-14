import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.modules.employees.models import Employee, EmployeeStatus
from app.modules.employees.repository import EmployeeRepository
from app.modules.employees.schemas import (
    AcceptInviteRequest,
    EmployeeActiveUpdate,
    EmployeeInviteRequest,
    EmployeeInviteResponse,
    EmployeeListItem,
    EmployeeListResponse,
    EmployeeRoleUpdate,
)
from app.modules.roles.models import User
from app.modules.roles.repository import RoleRepository
from app.modules.roles.schemas import ROLE_ADMIN, ROLE_CUSTOMER, ROLE_SUPER_ADMIN
from app.modules.users.repository import UserRepository

INVITE_TTL = timedelta(hours=48)
STAFF_ROLES = frozenset({ROLE_ADMIN, ROLE_SUPER_ADMIN})


def hash_invite_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _invite_base_url() -> str:
    """Storefront origin for invite/reset links (PUBLIC_APP_URL preferred)."""
    public = (settings.public_app_url or "").strip().rstrip("/")
    if public:
        return public
    origins = settings.cors_origin_list
    if origins:
        return origins[0].rstrip("/")
    if settings.is_production or settings.is_staging:
        raise RuntimeError(
            "PUBLIC_APP_URL is required for invite links in staging/production"
        )
    return "http://localhost:3000"


class EmployeeService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.employees = EmployeeRepository(db)
        self.users = UserRepository(db)
        self.roles = RoleRepository(db)

    def _to_list_item(self, employee: Employee) -> EmployeeListItem:
        user = employee.user
        if user is None:
            user = self.users.get_by_id(employee.user_id)
        assert user is not None
        return EmployeeListItem(
            id=employee.id,
            user_id=user.id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            job_title=employee.job_title,
            status=employee.status,
            is_active=user.is_active,
            roles=user.role_names,
            invited_at=employee.invited_at,
            accepted_at=employee.accepted_at,
        )

    def list_employees(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        q: str | None = None,
        status: str | None = None,
    ) -> EmployeeListResponse:
        from app.core.pagination import total_pages

        items, total = self.employees.list_employees(
            page=page,
            page_size=page_size,
            q=q,
            status=status,
        )
        return EmployeeListResponse(
            items=[self._to_list_item(e) for e in items],
            page=page,
            page_size=page_size,
            total=total,
            total_pages=total_pages(total, page_size),
        )

    def _build_invite_response(self, employee: Employee, token: str) -> EmployeeInviteResponse:
        item = self._to_list_item(employee)
        invite_url = None
        if not settings.is_production:
            invite_url = f"{_invite_base_url()}/accept-invite?token={token}"
        return EmployeeInviteResponse(**item.model_dump(), invite_url=invite_url)

    def _rotate_access_token(
        self, employee: Employee, user: User, *, invited_by: User
    ) -> str:
        """Invalidate current password and issue a fresh accept-invite token (48h)."""
        token = secrets.token_urlsafe(32)
        now = datetime.now(UTC)
        user.password_hash = hash_password(secrets.token_urlsafe(32))
        user.is_active = False
        employee.status = EmployeeStatus.INVITED.value
        employee.invited_by_user_id = invited_by.id
        employee.invite_token_hash = hash_invite_token(token)
        employee.invite_expires_at = now + INVITE_TTL
        employee.invited_at = now
        employee.accepted_at = None
        self.users.save(user)
        self.employees.save(employee)
        return token

    def invite(self, data: EmployeeInviteRequest, invited_by: User) -> EmployeeInviteResponse:
        self.roles.ensure_default_roles()
        staff_role = self.roles.get_by_name(data.role)
        if staff_role is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Staff roles are not seeded",
            )

        user = self.users.get_by_email(data.email)
        existing_employee = self.employees.get_by_user_id(user.id) if user else None
        if existing_employee is not None and existing_employee.status != EmployeeStatus.INACTIVE.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User is already an employee",
            )

        if user is None:
            user = User(
                email=data.email,
                password_hash=hash_password(secrets.token_urlsafe(32)),
                first_name=data.first_name,
                last_name=data.last_name,
                is_active=False,
                email_verified=False,
            )
            self.users.create(user)
        else:
            user.first_name = data.first_name
            user.last_name = data.last_name
            self.users.save(user)

        self.roles.remove_role_by_name(user.id, ROLE_CUSTOMER)
        for role_name in STAFF_ROLES:
            if role_name != data.role:
                self.roles.remove_role_by_name(user.id, role_name)
        self.roles.assign_role(user.id, staff_role)
        self.db.expire(user)

        user = self.users.get_by_id(user.id)
        assert user is not None

        if existing_employee is not None:
            employee = existing_employee
            employee.job_title = data.job_title
        else:
            employee = Employee(user_id=user.id, job_title=data.job_title)
            self.employees.create(employee)

        token = self._rotate_access_token(employee, user, invited_by=invited_by)
        self.db.commit()
        employee = self.employees.get_by_id(employee.id)
        assert employee is not None
        return self._build_invite_response(employee, token)

    def resend_invite(
        self, employee_id: UUID, invited_by: User
    ) -> EmployeeInviteResponse:
        employee = self.employees.get_by_id(employee_id)
        if employee is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
        if employee.status != EmployeeStatus.INVITED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only pending invitations can be resent; use password reset instead",
            )
        user = self.users.get_by_id(employee.user_id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        token = self._rotate_access_token(employee, user, invited_by=invited_by)
        self.db.commit()
        employee = self.employees.get_by_id(employee_id)
        assert employee is not None
        return self._build_invite_response(employee, token)

    def reset_password(
        self, employee_id: UUID, invited_by: User
    ) -> EmployeeInviteResponse:
        """Force password change via a new accept-invite link (invalidates old password)."""
        employee = self.employees.get_by_id(employee_id)
        if employee is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
        if employee.status == EmployeeStatus.INVITED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invitation still pending; use resend invite instead",
            )
        user = self.users.get_by_id(employee.user_id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        token = self._rotate_access_token(employee, user, invited_by=invited_by)
        self.db.commit()
        employee = self.employees.get_by_id(employee_id)
        assert employee is not None
        return self._build_invite_response(employee, token)

    def set_role(self, employee_id: UUID, data: EmployeeRoleUpdate) -> EmployeeListItem:
        employee = self.employees.get_by_id(employee_id)
        if employee is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
        user = self.users.get_by_id(employee.user_id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        if (
            ROLE_SUPER_ADMIN in user.role_names
            and data.role != ROLE_SUPER_ADMIN
            and self.employees.count_super_admins(exclude_user_id=user.id) < 1
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot demote the last SUPER_ADMIN",
            )

        staff_role = self.roles.get_by_name(data.role)
        if staff_role is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Staff roles are not seeded",
            )
        for role_name in STAFF_ROLES:
            if role_name != data.role:
                self.roles.remove_role_by_name(user.id, role_name)
        self.roles.assign_role(user.id, staff_role)
        self.db.commit()
        employee = self.employees.get_by_id(employee_id)
        assert employee is not None
        return self._to_list_item(employee)

    def set_active(self, employee_id: UUID, data: EmployeeActiveUpdate) -> EmployeeListItem:
        employee = self.employees.get_by_id(employee_id)
        if employee is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
        user = self.users.get_by_id(employee.user_id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        if (
            not data.is_active
            and ROLE_SUPER_ADMIN in user.role_names
            and self.employees.count_super_admins(exclude_user_id=user.id) < 1
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot deactivate the last SUPER_ADMIN",
            )

        if employee.status == EmployeeStatus.INVITED.value and data.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invited employees must accept the invite before activation",
            )

        user.is_active = data.is_active
        if data.is_active:
            employee.status = EmployeeStatus.ACTIVE.value
        else:
            employee.status = EmployeeStatus.INACTIVE.value
        self.users.save(user)
        self.employees.save(employee)
        self.db.commit()
        employee = self.employees.get_by_id(employee_id)
        assert employee is not None
        return self._to_list_item(employee)

    def accept_invite(self, data: AcceptInviteRequest) -> EmployeeListItem:
        token_hash = hash_invite_token(data.token)
        employee = self.employees.get_by_invite_token_hash(token_hash)
        if employee is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired invitation",
            )
        if employee.status != EmployeeStatus.INVITED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invitation is no longer pending",
            )
        expires = employee.invite_expires_at
        if expires is not None:
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=UTC)
            if expires < datetime.now(UTC):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid or expired invitation",
                )

        user = self.users.get_by_id(employee.user_id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        user.password_hash = hash_password(data.password)
        user.is_active = True
        user.email_verified = True
        employee.status = EmployeeStatus.ACTIVE.value
        employee.accepted_at = datetime.now(UTC)
        employee.invite_token_hash = None
        employee.invite_expires_at = None
        self.users.save(user)
        self.employees.save(employee)
        self.db.commit()
        employee = self.employees.get_by_id(employee.id)
        assert employee is not None
        return self._to_list_item(employee)
