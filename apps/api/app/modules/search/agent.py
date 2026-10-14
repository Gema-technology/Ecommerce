from __future__ import annotations

import json
import logging
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from app.modules.products.schemas import ProductSort
from app.modules.search.providers.base import LLMMessage, LLMProvider
from app.modules.search.schemas import SearchFilters
from app.modules.search.tools.catalog import TOOL_DEFINITIONS, CatalogTools

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "sales_assist.md"
_MAX_TOOL_ROUNDS = 4


def _load_system_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def _extract_json(text: str) -> dict[str, Any] | None:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return None
        try:
            data = json.loads(match.group(0))
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            return None


def _dec(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def parse_agent_payload(data: dict[str, Any]) -> tuple[str, SearchFilters, list[str], list[str]]:
    summary = str(data.get("summary") or "").strip()
    raw_filters = data.get("filters") if isinstance(data.get("filters"), dict) else {}
    sort_raw = str(raw_filters.get("sort") or "price_asc")
    try:
        sort = ProductSort(sort_raw)
    except ValueError:
        sort = ProductSort.PRICE_ASC

    filters = SearchFilters(
        search=raw_filters.get("search") or None,
        category=raw_filters.get("category") or None,
        brand=raw_filters.get("brand") or None,
        min_price=_dec(raw_filters.get("min_price")),
        max_price=_dec(raw_filters.get("max_price")),
        sort=sort,
    )
    labels = [str(x) for x in (data.get("labels") or []) if x]
    slugs = [str(x) for x in (data.get("product_slugs") or []) if x]
    return summary, filters, labels, slugs


class SalesAgent:
    def __init__(self, provider: LLMProvider, tools: CatalogTools) -> None:
        self.provider = provider
        self.tools = tools

    def run(self, query: str) -> tuple[str, SearchFilters, list[str], list[str]]:
        messages: list[LLMMessage] = [
            LLMMessage(role="system", content=_load_system_prompt()),
            LLMMessage(role="user", content=query),
        ]

        for _ in range(_MAX_TOOL_ROUNDS):
            response = self.provider.complete(messages, tools=TOOL_DEFINITIONS)
            if response.tool_calls:
                messages.append(
                    LLMMessage(
                        role="assistant",
                        content=response.content,
                        tool_calls=response.tool_calls,
                    )
                )
                for call in response.tool_calls:
                    result = self.tools.execute(call.name, call.arguments)
                    messages.append(
                        LLMMessage(
                            role="tool",
                            content=result,
                            tool_call_id=call.id,
                        )
                    )
                continue

            content = (response.content or "").strip()
            if not content:
                break
            data = _extract_json(content)
            if data is None:
                logger.warning("SalesAgent returned non-JSON content")
                break
            return parse_agent_payload(data)

        # Fallback from last tool search if model failed to finalize JSON
        payload = self.tools.last_search_payload or {}
        filters_used = payload.get("filters_used") or {}
        products = payload.get("products") or []
        sort_raw = str(filters_used.get("sort") or "price_asc")
        try:
            sort = ProductSort(sort_raw)
        except ValueError:
            sort = ProductSort.PRICE_ASC
        filters = SearchFilters(
            search=filters_used.get("search"),
            category=filters_used.get("category"),
            brand=filters_used.get("brand"),
            min_price=_dec(filters_used.get("min_price")),
            max_price=_dec(filters_used.get("max_price")),
            sort=sort,
        )
        labels: list[str] = []
        if filters.max_price is not None:
            labels.append(f"Hasta ${filters.max_price}")
        if filters.category:
            labels.append(filters.category.replace("-", " ").title())
        elif filters.search:
            labels.append(filters.search.title())
        slugs = [p["slug"] for p in products if p.get("slug")]
        summary = (
            f"Encontré {payload.get('total', len(products))} opciones según tu búsqueda."
            if products
            else "No encontré productos con esos criterios. Prueba ampliando el presupuesto o el término."
        )
        return summary, filters, labels, slugs
