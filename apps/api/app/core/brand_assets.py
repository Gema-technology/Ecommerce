"""Resolve company logo for PDF / print rendering."""

from __future__ import annotations

import base64
import mimetypes
from functools import lru_cache
from pathlib import Path

_BUNDLED_LOGO = Path(__file__).resolve().parents[1] / "assets" / "brand" / "gema_logo.jpg"


def resolve_business_logo_path(configured: str | None = None) -> Path | None:
    """Return first existing logo path: configured override, then bundled default."""
    candidates: list[Path] = []
    if configured and configured.strip():
        candidates.append(Path(configured.strip()))
    candidates.append(_BUNDLED_LOGO)
    for path in candidates:
        try:
            if path.is_file():
                return path.resolve()
        except OSError:
            continue
    return None


@lru_cache(maxsize=4)
def logo_data_uri(path_str: str) -> str:
    path = Path(path_str)
    mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def business_logo_data_uri(configured: str | None = None) -> str | None:
    path = resolve_business_logo_path(configured)
    if path is None:
        return None
    return logo_data_uri(str(path))
