from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.modules.users.schemas import normalize_email

StaffRole = Literal["ADMIN", "SUPER_ADMIN"]


class EmployeeListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    email: str
    first_name: str
    last_name: str
    job_title: str | None = None
    status: str
    is_active: bool
    roles: list[str] = Field(default_factory=list)
    invited_at: datetime | None = None
    accepted_at: datetime | None = None


class EmployeeListResponse(BaseModel):
    items: list[EmployeeListItem]
    page: int
    page_size: int
    total: int
    total_pages: int


class EmployeeInviteRequest(BaseModel):
    email: EmailStr
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    role: StaffRole = "ADMIN"
    job_title: str | None = Field(default=None, max_length=120)

    @field_validator("email")
    @classmethod
    def normalize(cls, value: EmailStr) -> str:
        return normalize_email(str(value))

    @field_validator("first_name", "last_name")
    @classmethod
    def strip_required(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Field cannot be empty")
        return cleaned

    @field_validator("job_title")
    @classmethod
    def strip_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class EmployeeInviteResponse(EmployeeListItem):
    invite_url: str | None = None


class EmployeeRoleUpdate(BaseModel):
    role: StaffRole


class EmployeeActiveUpdate(BaseModel):
    is_active: bool


class AcceptInviteRequest(BaseModel):
    token: str = Field(min_length=16, max_length=200)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if value.strip() != value:
            raise ValueError("Password cannot start or end with whitespace")
        return value
