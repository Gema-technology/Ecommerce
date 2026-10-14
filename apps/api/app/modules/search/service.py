from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.brands.service import BrandService
from app.modules.categories.service import CategoryService
from app.modules.products.schemas import ProductRead, ProductSort
from app.modules.products.service import ProductService
from app.modules.search.agent import SalesAgent
from app.modules.search.parser import parse_search_intent
from app.modules.search.providers import get_llm_provider
from app.modules.search.schemas import (
    AssistProduct,
    SearchAssistResponse,
    SearchFilters,
)
from app.modules.search.tools.catalog import CatalogTools

logger = logging.getLogger(__name__)


class SearchAssistService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.products = ProductService(db)
        self.categories = CategoryService(db)
        self.brands = BrandService(db)

    def assist(self, query: str) -> SearchAssistResponse:
        query = query.strip()
        provider = get_llm_provider()
        if provider is not None:
            try:
                return self._assist_with_agent(query, provider)
            except Exception:
                logger.exception("Sales agent failed; falling back to rules")

        return self._assist_with_rules(query)

    def _catalog_slug_sets(self) -> tuple[set[str], set[str]]:
        cats = {c.slug for c in self.categories.list_categories(active_only=True)}
        brands = {b.slug for b in self.brands.list_brands(active_only=True)}
        return cats, brands

    def _assist_with_rules(self, query: str) -> SearchAssistResponse:
        cat_slugs, brand_slugs = self._catalog_slug_sets()
        filters, labels = parse_search_intent(
            query,
            category_slugs=cat_slugs,
            brand_slugs=brand_slugs,
        )
        # If synonym suggests a category that exists, prefer category filter
        filters = self._prefer_category_from_search(filters, cat_slugs)
        products = self._load_products(filters)
        summary = self._rules_summary(query, filters, products, labels)
        return SearchAssistResponse(
            query=query,
            summary=summary,
            filters=filters,
            labels=labels,
            products=[self._to_assist(p) for p in products],
            source="rules",
        )

    def _assist_with_agent(self, query: str, provider: object) -> SearchAssistResponse:
        tools = CatalogTools(self.db)
        agent = SalesAgent(provider, tools)  # type: ignore[arg-type]
        summary, filters, labels, slugs = agent.run(query)

        products: list[ProductRead] = []
        if slugs:
            by_slug = {p.slug: p for p in self._load_products(filters, page_size=12)}
            # Also resolve any missing slugs individually via list search
            for slug in slugs:
                if slug in by_slug:
                    products.append(by_slug[slug])
                    continue
                found = self.products.list_products(
                    search=slug,
                    sort=ProductSort.RELEVANCE,
                    page=1,
                    page_size=5,
                    is_active=True,
                )
                match = next((p for p in found.items if p.slug == slug), None)
                if match:
                    products.append(match)
        if not products:
            products = self._load_products(filters)

        if not summary:
            summary = self._rules_summary(query, filters, products, labels)

        return SearchAssistResponse(
            query=query,
            summary=summary,
            filters=filters,
            labels=labels,
            products=[self._to_assist(p) for p in products[:8]],
            source="agent",
        )

    def _prefer_category_from_search(
        self,
        filters: SearchFilters,
        category_slugs: set[str],
    ) -> SearchFilters:
        if filters.category or not filters.search:
            return filters
        tokens = filters.search.lower().split()
        for token in tokens:
            if token in category_slugs:
                remaining = [t for t in tokens if t != token]
                return filters.model_copy(
                    update={
                        "category": token,
                        "search": " ".join(remaining) or None,
                    }
                )
        return filters

    def _load_products(
        self,
        filters: SearchFilters,
        *,
        page_size: int = 8,
    ) -> list[ProductRead]:
        result = self.products.list_products(
            category=filters.category,
            brand=filters.brand,
            search=filters.search,
            min_price=filters.min_price,
            max_price=filters.max_price,
            sort=filters.sort,
            page=1,
            page_size=page_size,
            is_active=True,
        )
        return result.items

    @staticmethod
    def _rules_summary(
        query: str,
        filters: SearchFilters,
        products: list[ProductRead],
        labels: list[str],
    ) -> str:
        if not products:
            budget = f" con presupuesto hasta ${filters.max_price}" if filters.max_price else ""
            return (
                f"No encontré productos que coincidan{budget}. "
                "Prueba ampliando el presupuesto o el término de búsqueda."
            )
        focus = labels[0] if labels else (filters.search or "tu búsqueda")
        budget = f" hasta ${filters.max_price}" if filters.max_price else ""
        count = len(products)
        return (
            f"Con{budget} te propongo {count} opción"
            f"{'' if count == 1 else 'es'} de {focus.lower()}."
            if budget
            else f"Encontré {count} opción{'' if count == 1 else 'es'} para {focus.lower()}."
        )

    @staticmethod
    def _to_assist(product: ProductRead) -> AssistProduct:
        primary = next((i for i in product.images if i.is_primary), None)
        if primary is None and product.images:
            primary = product.images[0]
        return AssistProduct(
            id=product.id if isinstance(product.id, UUID) else UUID(str(product.id)),
            name=product.name,
            slug=product.slug,
            short_description=product.short_description,
            brand_name=product.brand.name if product.brand else None,
            category_name=product.category.name if product.category else None,
            image_url=primary.url if primary else None,
            price=product.price,
            availability=product.availability,
        )
