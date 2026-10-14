"""Timezone helpers for comprobantes electrónicos (Ecuador mainland)."""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

# SRI fiscal documents use mainland Ecuador civil date (no DST).
ECUADOR_TZ = ZoneInfo("America/Guayaquil")


def ecuador_now(*, reference: datetime | None = None) -> datetime:
    """Current instant in America/Guayaquil (aware)."""
    if reference is None:
        reference = datetime.now(tz=ECUADOR_TZ)
    elif reference.tzinfo is None:
        reference = reference.replace(tzinfo=ECUADOR_TZ)
    else:
        reference = reference.astimezone(ECUADOR_TZ)
    return reference


def ecuador_emission_date(*, reference: datetime | None = None) -> date:
    """Calendar date for clave de acceso / fechaEmision (dd/mm/yyyy)."""
    return ecuador_now(reference=reference).date()
