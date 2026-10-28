from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.auth.dependencies import RequireAdmin, RequireSuperAdmin
from app.modules.employees.schemas import (
    EmployeeActiveUpdate,
    EmployeeInviteRequest,
    EmployeeInviteResponse,
    EmployeeListItem,
    EmployeeListResponse,
    EmployeeRoleUpdate,
)
from app.modules.employees.service import EmployeeService

router = APIRouter(tags=["employees"])


@router.get("/admin/employees", response_model=EmployeeListResponse)
def list_employees(
    _admin: RequireAdmin,
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    q: str | None = Query(default=None),
    status: str | None = Query(default=None),
) -> EmployeeListResponse:
    return EmployeeService(db).list_employees(
        page=page,
        page_size=page_size,
        q=q,
        status=status,
    )


@router.post("/admin/employees/invite", response_model=EmployeeInviteResponse, status_code=201)
def invite_employee(
    payload: EmployeeInviteRequest,
    admin: RequireSuperAdmin,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> EmployeeInviteResponse:
    return EmployeeService(db).invite(payload, admin, request)


@router.patch("/admin/employees/{employee_id}/role", response_model=EmployeeListItem)
def set_employee_role(
    employee_id: UUID,
    payload: EmployeeRoleUpdate,
    _admin: RequireSuperAdmin,
    db: Annotated[Session, Depends(get_db)],
) -> EmployeeListItem:
    return EmployeeService(db).set_role(employee_id, payload)


@router.post(
    "/admin/employees/{employee_id}/resend-invite",
    response_model=EmployeeInviteResponse,
)
def resend_employee_invite(
    employee_id: UUID,
    admin: RequireSuperAdmin,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> EmployeeInviteResponse:
    """Regenerate invite link for a pending (invited) employee."""
    return EmployeeService(db).resend_invite(employee_id, admin, request)


@router.post(
    "/admin/employees/{employee_id}/reset-password",
    response_model=EmployeeInviteResponse,
)
def reset_employee_password(
    employee_id: UUID,
    admin: RequireSuperAdmin,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> EmployeeInviteResponse:
    """Invalidate password and issue a new set-password link (48h)."""
    return EmployeeService(db).reset_password(employee_id, admin, request)


@router.patch("/admin/employees/{employee_id}/active", response_model=EmployeeListItem)
def set_employee_active(
    employee_id: UUID,
    payload: EmployeeActiveUpdate,
    _admin: RequireAdmin,
    db: Annotated[Session, Depends(get_db)],
) -> EmployeeListItem:
    return EmployeeService(db).set_active(employee_id, payload)
