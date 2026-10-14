from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.modules.pricing.schemas import PublicPrice
from app.modules.products.schemas import AvailabilityStatus, ProductSort


class SearchAssistRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)


class SearchFilters(BaseModel):
    search: str | None = None
    category: str | None = None
    brand: str | None = None
    min_price: Decimal | None = None
    max_price: Decimal | None = None
    sort: ProductSort = ProductSort.PRICE_ASC


class AssistProduct(BaseModel):
    id: UUID
    name: str
    slug: str
    short_description: str | None = None
    brand_name: str | None = None
    category_name: str | None = None
    image_url: str | None = None
    price: PublicPrice | None = None
    availability: AvailabilityStatus = AvailabilityStatus.UNKNOWN


class SearchAssistResponse(BaseModel):
    query: str
    summary: str
    filters: SearchFilters
    labels: list[str] = Field(default_factory=list)
    products: list[AssistProduct] = Field(default_factory=list)
    source: str = "rules"  # rules | agent
