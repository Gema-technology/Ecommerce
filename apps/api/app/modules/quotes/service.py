from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.modules.quotes.models import Quote, QuoteItem, QuoteProduct
from app.modules.quotes.pricing import (
    compute_quote_totals,
    compute_tier_prices,
    quantize_money,
    resolve_unit_price,
)
from app.modules.quotes.repository import QuoteRepository
from app.modules.quotes.schemas import (
    PricingConfigRead,
    PricingConfigUpdate,
    QuoteCreate,
    QuoteItemCreate,
    QuoteListResponse,
    QuoteProductCreate,
    QuoteProductListResponse,
    QuoteProductRead,
    QuoteProductUpdate,
    QuoteRead,
    QuoteUpdate,
)
from app.modules.roles.models import User


class QuoteService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = QuoteRepository(db)

    def _config(self):
        return self.repo.get_or_create_pricing_config()

    def get_pricing_config(self) -> PricingConfigRead:
        return PricingConfigRead.model_validate(self._config())

    def update_pricing_config(self, payload: PricingConfigUpdate) -> PricingConfigRead:
        config = self._config()
        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(config, key, value)
        self.db.commit()
        self.db.refresh(config)
        return PricingConfigRead.model_validate(config)

    def _product_read(self, product: QuoteProduct) -> QuoteProductRead:
        config = self._config()
        prices = compute_tier_prices(
            product.cost_price,
            product.other_costs,
            min_margin=config.min_margin,
            rec_margin=config.rec_margin,
            high_margin=config.high_margin,
        )
        return QuoteProductRead(
            id=product.id,
            name=product.name,
            category=product.category,
            cost_price=product.cost_price,
            other_costs=product.other_costs,
            is_active=product.is_active,
            created_at=product.created_at,
            updated_at=product.updated_at,
            cost_real=prices["cost_real"],
            price_min=prices["price_min"],
            price_rec=prices["price_rec"],
            price_high=prices["price_high"],
        )

    def list_products(
        self,
        *,
        q: str | None = None,
        page: int = 1,
        page_size: int = 20,
        active_only: bool = False,
    ) -> QuoteProductListResponse:
        items, total = self.repo.list_products(
            q=q, page=page, page_size=page_size, active_only=active_only
        )
        return QuoteProductListResponse(
            items=[self._product_read(p) for p in items],
            page=page,
            page_size=page_size,
            total=total,
            total_pages=self.repo.total_pages(total, page_size),
        )

    def create_product(self, payload: QuoteProductCreate) -> QuoteProductRead:
        product = QuoteProduct(
            name=payload.name.strip(),
            category=payload.category.strip() if payload.category else None,
            cost_price=quantize_money(payload.cost_price),
            other_costs=quantize_money(payload.other_costs),
            is_active=payload.is_active,
        )
        self.repo.add_product(product)
        self.db.commit()
        self.db.refresh(product)
        return self._product_read(product)

    def update_product(self, product_id: UUID, payload: QuoteProductUpdate) -> QuoteProductRead:
        product = self.repo.get_product(product_id)
        if product is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
        data = payload.model_dump(exclude_unset=True)
        if "name" in data and data["name"] is not None:
            data["name"] = data["name"].strip()
        if "category" in data and data["category"] is not None:
            data["category"] = data["category"].strip() or None
        if "cost_price" in data and data["cost_price"] is not None:
            data["cost_price"] = quantize_money(data["cost_price"])
        if "other_costs" in data and data["other_costs"] is not None:
            data["other_costs"] = quantize_money(data["other_costs"])
        for key, value in data.items():
            setattr(product, key, value)
        self.db.commit()
        self.db.refresh(product)
        return self._product_read(product)

    def delete_product(self, product_id: UUID) -> None:
        product = self.repo.get_product(product_id)
        if product is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
        self.repo.delete_product(product)
        self.db.commit()

    def _resolve_item(
        self,
        item: QuoteItemCreate,
        config,
    ) -> tuple[str, Decimal, int, UUID | None]:
        tier = item.tier.value
        quantity = item.quantity
        product_id: UUID | None = item.product_id

        if product_id is not None:
            product = self.repo.get_product(product_id)
            if product is None or not product.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Product {product_id} not found or inactive",
                )
            product_name = product.name
            unit_price = resolve_unit_price(
                product,
                tier,
                min_margin=config.min_margin,
                rec_margin=config.rec_margin,
                high_margin=config.high_margin,
                manual_price=item.unit_price,
            )
            return product_name, unit_price, quantity, product_id

        if not item.product_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="product_name required when product_id is omitted",
            )
        if item.unit_price is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="unit_price required for custom line items",
            )
        return item.product_name.strip(), quantize_money(item.unit_price), quantity, None

    def _build_items(
        self,
        payload_items: list[QuoteItemCreate],
        config,
    ) -> list[QuoteItem]:
        built: list[QuoteItem] = []
        totals_input: list[tuple[int, Decimal]] = []
        for raw in payload_items:
            product_name, unit_price, quantity, product_id = self._resolve_item(raw, config)
            line_total = quantize_money(unit_price * quantity)
            built.append(
                QuoteItem(
                    product_id=product_id,
                    product_name=product_name,
                    tier=raw.tier.value,
                    quantity=quantity,
                    unit_price=unit_price,
                    line_total=line_total,
                )
            )
            totals_input.append((quantity, unit_price))
        return built

    def _quote_read(self, quote: Quote) -> QuoteRead:
        return QuoteRead(
            id=quote.id,
            number=quote.number,
            client_name=quote.client_name,
            client_id_number=quote.client_id_number,
            client_phone=quote.client_phone,
            client_email=quote.client_email,
            client_address=quote.client_address,
            iva_pct=quote.iva_pct,
            subtotal=quote.subtotal,
            iva_amount=quote.iva_amount,
            total=quote.total,
            status=quote.status,
            valid_until=quote.valid_until,
            notes=quote.notes,
            created_by=quote.created_by,
            created_at=quote.created_at,
            items=list(quote.items),
            created_by_email=quote.created_by_user.email if quote.created_by_user else None,
        )

    def create_quote(self, payload: QuoteCreate, user: User) -> QuoteRead:
        config = self._config()
        iva_pct = payload.iva_pct if payload.iva_pct is not None else config.default_iva

        built_items = self._build_items(payload.items, config)
        totals_input = [(item.quantity, item.unit_price) for item in built_items]
        subtotal, iva_amount, total = compute_quote_totals(totals_input, iva_pct)

        number = self.repo.next_quote_number()
        quote = Quote(
            number=number,
            client_name=payload.client_name,
            client_id_number=payload.client_id_number,
            client_phone=payload.client_phone,
            client_email=payload.client_email,
            client_address=payload.client_address,
            iva_pct=iva_pct,
            subtotal=subtotal,
            iva_amount=iva_amount,
            total=total,
            status=payload.status.value,
            valid_until=payload.valid_until,
            notes=payload.notes,
            created_by=user.id,
            items=built_items,
        )
        self.repo.add_quote(quote)
        self.db.commit()
        loaded = self.repo.get_quote(quote.id)
        assert loaded is not None
        return self._quote_read(loaded)

    def list_quotes(
        self,
        *,
        status: str | None = None,
        client: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> QuoteListResponse:
        items, total = self.repo.list_quotes(
            status=status,
            client=client,
            date_from=date_from,
            date_to=date_to,
            page=page,
            page_size=page_size,
        )
        return QuoteListResponse(
            items=[self._quote_read(q) for q in items],
            page=page,
            page_size=page_size,
            total=total,
            total_pages=self.repo.total_pages(total, page_size),
        )

    def get_quote(self, quote_id: UUID) -> QuoteRead:
        quote = self.repo.get_quote(quote_id)
        if quote is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quote not found")
        return self._quote_read(quote)

    def update_quote(self, quote_id: UUID, payload: QuoteUpdate) -> QuoteRead:
        quote = self.repo.get_quote(quote_id)
        if quote is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quote not found")

        config = self._config()
        data = payload.model_dump(exclude_unset=True)
        items_payload = data.pop("items", None)
        status_value = data.pop("status", None)
        if status_value is not None:
            quote.status = status_value.value if hasattr(status_value, "value") else status_value

        for key, value in data.items():
            setattr(quote, key, value)

        if items_payload is not None:
            quote.items.clear()
            self.db.flush()
            built = self._build_items([QuoteItemCreate.model_validate(i) for i in items_payload], config)
            quote.items.extend(built)
            iva_pct = quote.iva_pct
            totals_input = [(item.quantity, item.unit_price) for item in built]
            subtotal, iva_amount, total = compute_quote_totals(totals_input, iva_pct)
            quote.subtotal = subtotal
            quote.iva_amount = iva_amount
            quote.total = total
        elif "iva_pct" in data:
            totals_input = [(item.quantity, item.unit_price) for item in quote.items]
            subtotal, iva_amount, total = compute_quote_totals(totals_input, quote.iva_pct)
            quote.subtotal = subtotal
            quote.iva_amount = iva_amount
            quote.total = total

        self.db.commit()
        loaded = self.repo.get_quote(quote_id)
        assert loaded is not None
        return self._quote_read(loaded)

    def delete_quote(self, quote_id: UUID) -> None:
        quote = self.repo.get_quote(quote_id)
        if quote is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quote not found")
        self.repo.delete_quote(quote)
        self.db.commit()

    def get_quote_entity(self, quote_id: UUID) -> Quote:
        quote = self.repo.get_quote(quote_id)
        if quote is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quote not found")
        return quote
