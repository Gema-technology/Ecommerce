import re
import unicodedata


def slugify(value: str, *, max_length: int = 200) -> str:
    """Convert text to a URL-safe slug."""
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_text.lower()).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)
    return slug[:max_length].rstrip("-") or "item"


def normalize_sku(value: str) -> str:
    return re.sub(r"\s+", "", value.strip().upper())
