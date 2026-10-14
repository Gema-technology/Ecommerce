from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.modules.inventory.models import MovementDirection, MovementType


class LocationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    code: str = Field(min_length=1, max_length=50)
    description: str | None = None
    city: str | None = Field(default=None, max_length=100)
    province: str | None = Field(default=None, max_length=100)
    country: str = Field(default="Ecuador", min_length=1, max_length=100)
    is_active: bool = True

    @field_validator("name", "country")
    @classmethod
    def normalize_required(cls, value: str) -> str:
        cleaned = " ".join(value.strip().split())
        if not cleaned:
            raise ValueError("Field cannot be empty")
        return cleaned

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        cleaned = value.strip().upper().replace(" ", "-")
        if not cleaned:
            raise ValueError("code cannot be empty")
        return cleaned


class LocationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    code: str
    description: str | None
    city: str | None
    province: str | None
    country: str
    is_active: bool


class LocationBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    code: str
    city: str | None


class InventoryCreate(BaseModel):
    product_id: UUID
    location_id: UUID | None = None
    reorder_point: int = Field(default=0, ge=0)
    reorder_quantity: int = Field(default=0, ge=0)


class InventoryThresholdUpdate(BaseModel):
    reorder_point: int | None = Field(default=None, ge=0)
    reorder_quantity: int | None = Field(default=None, ge=0)


class InventoryRead(BaseModel):
    id: UUID
    product_id: UUID
    product_name: str
    product_sku: str
    location: LocationBrief
    quantity: int
    reserved_quantity: int
    available_quantity: int
    reorder_point: int
    reorder_quantity: int


class MovementRequest(BaseModel):
    quantity: int = Field(gt=0)
    location_id: UUID | None = None
    reference_type: str | None = Field(default=None, max_length=50)
    reference_id: str | None = Field(default=None, max_length=100)
    notes: str | None = None


class AdjustmentRequest(BaseModel):
    """Signed delta: positive increases on-hand, negative decreases."""

    delta: int
    location_id: UUID | None = None
    reference_type: str | None = Field(default=None, max_length=50)
    reference_id: str | None = Field(default=None, max_length=100)
    notes: str | None = None

    @model_validator(mode="after")
    def delta_nonzero(self) -> "AdjustmentRequest":
        if self.delta == 0:
            raise ValueError("delta cannot be zero")
        return self


class InventoryMovementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    inventory_id: UUID
    type: MovementType
    quantity: int
    direction: MovementDirection
    signed_quantity: int
    reference_type: str | None
    reference_id: str | None
    notes: str | None
    created_by: UUID
    created_by_email: str | None = None
    created_at: datetime


class MovementListResponse(BaseModel):
    items: list[InventoryMovementRead]
    page: int
    page_size: int
    total: int
    total_pages: int


class InventoryListResponse(BaseModel):
    items: list[InventoryRead]
    page: int
    page_size: int
    total: int
    total_pages: int


class LocationListResponse(BaseModel):
    items: list[LocationRead]
    page: int
    page_size: int
    total: int
    total_pages: int


class InventoryOperationResponse(BaseModel):
    inventory: InventoryRead
    movement: InventoryMovementRead


class ExpireReservationsResponse(BaseModel):
    expired_reservations: int
    cancelled_orders: int
