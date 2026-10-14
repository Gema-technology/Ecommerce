"""HTTP client for PayPhone (Ecuador) REST APIs."""

from __future__ import annotations

import json
import logging
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)


class PayPhoneHttpClient(Protocol):
    def request(
        self,
        method: str,
        path: str,
        *,
        token: str,
        json_body: dict[str, Any] | None = None,
    ) -> Any: ...


class UrllibPayPhoneClient:
    """stdlib HTTP client — no extra runtime dependency."""

    def __init__(self, base_url: str, *, timeout_seconds: float = 30.0) -> None:
        self._base = base_url.rstrip("/")
        self._timeout = timeout_seconds

    def request(
        self,
        method: str,
        path: str,
        *,
        token: str,
        json_body: dict[str, Any] | None = None,
    ) -> Any:
        url = f"{self._base}{path}"
        data = None
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if json_body is not None:
            data = json.dumps(json_body).encode("utf-8")
        req = Request(url, data=data, headers=headers, method=method.upper())
        try:
            with urlopen(req, timeout=self._timeout) as resp:  # noqa: S310 — HTTPS API host
                raw = resp.read()
                content_type = resp.headers.get("Content-Type", "")
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            logger.warning("PayPhone HTTP %s on %s %s", exc.code, method, path)
            raise PayPhoneApiError(exc.code, detail) from exc
        except URLError as exc:
            logger.warning("PayPhone unreachable: %s", type(exc.reason).__name__)
            raise PayPhoneApiError(503, "PayPhone API unreachable") from exc

        if not raw:
            return None
        text = raw.decode("utf-8")
        # API Links may return a bare JSON string URL.
        if "application/json" in content_type or text[:1] in "{\"[":
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return text.strip().strip('"')
        return text.strip().strip('"')


class PayPhoneApiError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)
