"""Spanish rule-based intent parser for storefront search."""

from __future__ import annotations

import re
import unicodedata
from decimal import Decimal, InvalidOperation

from app.modules.products.schemas import ProductSort
from app.modules.search.schemas import SearchFilters

_STOPWORDS = frozenset(
    {
        "tengo",
        "tenemos",
        "presupuesto",
        "de",
        "del",
        "y",
        "quiero",
        "queremos",
        "busco",
        "buscamos",
        "necesito",
        "necesitamos",
        "unos",
        "unas",
        "un",
        "una",
        "el",
        "la",
        "los",
        "las",
        "me",
        "mi",
        "mis",
        "para",
        "con",
        "por",
        "en",
        "al",
        "a",
        "que",
        "como",
        "más",
        "mas",
        "menos",
        "hasta",
        "máximo",
        "maximo",
        "mínimo",
        "minimo",
        "entre",
        "usd",
        "dolares",
        "dólares",
        "dolar",
        "dólar",
        "precio",
        "precios",
        "algo",
        "algunos",
        "algunas",
        "favor",
        "porfa",
        "porfavor",
        "hola",
        "buenas",
        "buenos",
        "dias",
        "días",
        "tardes",
    }
)

# Canonical term -> aliases (normalized, no accents)
_SYNONYMS: dict[str, tuple[str, ...]] = {
    "audifonos": ("audifonos", "audifono", "headphones", "auriculares", "auricular", "headset"),
    "laptops": ("laptop", "laptops", "portatil", "portatiles", "notebook", "notebooks"),
    "monitores": ("monitor", "monitores", "pantalla", "pantallas", "display"),
    "mouse": ("mouse", "raton", "ratones"),
    "teclados": ("teclado", "teclados", "keyboard"),
    "ssd": ("ssd", "disco", "discos", "almacenamiento"),
    "gpu": ("gpu", "tarjeta", "graficas", "grafica", "rtx", "gtx"),
    "gaming": ("gaming", "gamer"),
}

_CANONICAL_LABELS: dict[str, str] = {
    "audifonos": "Audífonos",
    "laptops": "Laptops",
    "monitores": "Monitores",
    "mouse": "Mouse",
    "teclados": "Teclados",
    "ssd": "SSD",
    "gpu": "GPU",
    "gaming": "Gaming",
}

_ALIAS_TO_CANONICAL: dict[str, str] = {
    alias: canon for canon, aliases in _SYNONYMS.items() for alias in aliases
}

_BUDGET_MAX_RE = re.compile(
    r"(?:presupuesto\s+(?:de\s+|hasta\s+)?|hasta\s+|m[aá]ximo\s+|menos\s+de\s+)"
    r"\$?\s*(\d+(?:[.,]\d+)?)",
    re.IGNORECASE,
)
_BUDGET_MIN_RE = re.compile(
    r"(?:desde\s+|m[ií]nimo\s+)\s*\$?\s*(\d+(?:[.,]\d+)?)",
    re.IGNORECASE,
)
_RANGE_RE = re.compile(
    r"entre\s+\$?\s*(\d+(?:[.,]\d+)?)\s+y\s+\$?\s*(\d+(?:[.,]\d+)?)",
    re.IGNORECASE,
)
_BARE_MONEY_RE = re.compile(r"\$\s*(\d+(?:[.,]\d+)?)")


def normalize_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.strip().lower())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def _parse_money(raw: str) -> Decimal | None:
    try:
        return Decimal(raw.replace(",", "."))
    except (InvalidOperation, AttributeError):
        return None


def _extract_terms(normalized: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9]+", normalized)
    terms: list[str] = []
    for token in tokens:
        if token.isdigit():
            continue
        if token in _STOPWORDS:
            continue
        if len(token) < 2:
            continue
        terms.append(_ALIAS_TO_CANONICAL.get(token, token))
    # Dedupe preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for term in terms:
        if term not in seen:
            seen.add(term)
            unique.append(term)
    return unique


def parse_search_intent(
    query: str,
    *,
    category_slugs: set[str] | None = None,
    brand_slugs: set[str] | None = None,
) -> tuple[SearchFilters, list[str]]:
    """Return filters + human labels for a natural-language query."""
    original = query.strip()
    normalized = normalize_text(original)
    labels: list[str] = []

    min_price: Decimal | None = None
    max_price: Decimal | None = None
    sort = ProductSort.RELEVANCE

    range_match = _RANGE_RE.search(normalized)
    if range_match:
        a = _parse_money(range_match.group(1))
        b = _parse_money(range_match.group(2))
        if a is not None and b is not None:
            min_price, max_price = (a, b) if a <= b else (b, a)
            labels.append(f"Entre ${min_price} y ${max_price}")
            sort = ProductSort.PRICE_ASC

    if max_price is None:
        max_match = _BUDGET_MAX_RE.search(normalized)
        if max_match:
            max_price = _parse_money(max_match.group(1))
            if max_price is not None:
                labels.append(f"Hasta ${max_price}")
                sort = ProductSort.PRICE_ASC

    if min_price is None:
        min_match = _BUDGET_MIN_RE.search(normalized)
        if min_match:
            min_price = _parse_money(min_match.group(1))
            if min_price is not None and f"Desde ${min_price}" not in labels:
                labels.append(f"Desde ${min_price}")

    if max_price is None and min_price is None:
        money = _BARE_MONEY_RE.search(normalized)
        if money and ("presupuesto" in normalized or "hasta" in normalized):
            max_price = _parse_money(money.group(1))
            if max_price is not None:
                labels.append(f"Hasta ${max_price}")
                sort = ProductSort.PRICE_ASC

    if re.search(r"\b(barato|baratos|economico|economicos|econ[oó]mico)\b", normalized):
        sort = ProductSort.PRICE_ASC
        if "Más baratos" not in labels:
            labels.append("Más baratos")
    elif re.search(r"\b(caro|caros|premium|mejor)\b", normalized):
        sort = ProductSort.PRICE_DESC
        if "Mayor precio" not in labels:
            labels.append("Mayor precio")

    terms = _extract_terms(normalized)
    category_slugs = category_slugs or set()
    brand_slugs = brand_slugs or set()

    category: str | None = None
    brand: str | None = None
    search_terms: list[str] = []

    for term in terms:
        if term in category_slugs and category is None:
            category = term
            labels.append(_CANONICAL_LABELS.get(term, term.replace("-", " ").title()))
            continue
        if term in brand_slugs and brand is None:
            brand = term
            labels.append(term.replace("-", " ").title())
            continue
        search_terms.append(term)
        if term in _CANONICAL_LABELS:
            label = _CANONICAL_LABELS[term]
            if label not in labels:
                labels.append(label)

    search = " ".join(search_terms) if search_terms else None

    # If we only matched category/brand and no free text, that's fine.
    # If nothing structured was found, fall back to full query as search.
    has_structure = any([category, brand, search, min_price is not None, max_price is not None])
    if not has_structure:
        search = original
        sort = ProductSort.RELEVANCE

    # Prefer category over stuffing product type into search when synonym matched a slug
    if category and search and search.strip() == category:
        search = None

    filters = SearchFilters(
        search=search,
        category=category,
        brand=brand,
        min_price=min_price,
        max_price=max_price,
        sort=sort,
    )
    return filters, labels
