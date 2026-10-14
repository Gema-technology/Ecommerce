"""Catalog tools callable by the sales agent."""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy.orm import Session

from app.modules.brands.service import BrandService
from app.modules.categories.service import CategoryService
from app.modules.products.schemas import ProductSort
from app.modules.products.service import ProductService

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_products",
            "description": (
                "Search the live GEMA catalog. Use for recommending products. "
                "Prices and stock come only from this tool."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "search": {
                        "type": "string",
                        "description": "Free-text product keywords (no filler words).",
                    },
                    "category": {
                        "type": "string",
                        "description": "Category slug if known (e.g. audifonos, laptops).",
                    },
                    "brand": {"type": "string", "description": "Brand slug if known."},
                    "min_price": {
                        "type": "number",
                        "description": "Minimum price in USD.",
                    },
                    "max_price": {
                        "type": "number",
                        "description": "Maximum budget / price in USD.",
                    },
                    "sort": {
                        "type": "string",
                        "enum": [
                            "relevance",
                            "price_asc",
                            "price_desc",
                            "name_asc",
                            "name_desc",
                            "newest",
                        ],
                    },
                    "page_size": {
                        "type": "integer",
                        "description": "How many products to return (1-12).",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_categories",
            "description": "List active category names and slugs.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


def _dec(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


class CatalogTools:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.products = ProductService(db)
        self.categories = CategoryService(db)
        self.brands = BrandService(db)
        self.last_search_payload: dict[str, Any] | None = None

    def execute(self, name: str, arguments: dict[str, Any]) -> str:
        if name == "search_products":
            return self._search_products(arguments)
        if name == "list_categories":
            return self._list_categories()
        return json.dumps({"error": f"Unknown tool: {name}"})

    def _list_categories(self) -> str:
        cats = self.categories.list_categories(active_only=True)
        payload = [{"name": c.name, "slug": c.slug} for c in cats[:50]]
        return json.dumps({"categories": payload}, ensure_ascii=False)

    def _search_products(self, args: dict[str, Any]) -> str:
        sort_raw = str(args.get("sort") or "price_asc")
        try:
            sort = ProductSort(sort_raw)
        except ValueError:
            sort = ProductSort.PRICE_ASC

        page_size = int(args.get("page_size") or 8)
        page_size = min(max(page_size, 1), 12)

        result = self.products.list_products(
            category=args.get("category") or None,
            brand=args.get("brand") or None,
            search=args.get("search") or None,
            min_price=_dec(args.get("min_price")),
            max_price=_dec(args.get("max_price")),
            sort=sort,
            page=1,
            page_size=page_size,
            is_active=True,
        )
        items = []
        for p in result.items:
            primary = next((i for i in p.images if i.is_primary), None)
            if primary is None and p.images:
                primary = p.images[0]
            items.append(
                {
                    "id": str(p.id),
                    "name": p.name,
                    "slug": p.slug,
                    "short_description": p.short_description,
                    "brand": p.brand.name,
                    "category": p.category.name,
                    "category_slug": p.category.slug,
                    "brand_slug": p.brand.slug,
                    "price": p.price.amount if p.price else None,
                    "currency": p.price.currency if p.price else None,
                    "availability": p.availability.value,
                    "image_url": primary.url if primary else None,
                }
            )
        payload = {
            "total": result.total,
            "filters_used": {
                "search": args.get("search"),
                "category": args.get("category"),
                "brand": args.get("brand"),
                "min_price": args.get("min_price"),
                "max_price": args.get("max_price"),
                "sort": sort.value,
            },
            "products": items,
        }
        self.last_search_payload = payload
        return json.dumps(payload, ensure_ascii=False)
