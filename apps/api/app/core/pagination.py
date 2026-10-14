"""Shared pagination helpers for admin list endpoints."""

from __future__ import annotations

import math


def total_pages(total: int, page_size: int) -> int:
    if page_size <= 0:
        return 0
    return math.ceil(total / page_size) if total else 0


def offset_for(page: int, page_size: int) -> int:
    return max(0, (max(1, page) - 1) * page_size)
