"""Unit tests for the external reservation-expire HTTP caller (no Postgres/Redis)."""

from __future__ import annotations

import io
import json
import logging
from urllib.error import HTTPError, URLError

import pytest

from app.scripts import expire_reservations as job


class _FakeResponse:
    def __init__(self, status: int, body: bytes) -> None:
        self.status = status
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None


def test_run_once_success(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    secret = "unit-test-internal-secret"
    captured: dict[str, object] = {}

    def fake_urlopen(request: object, timeout: float = 0) -> _FakeResponse:
        captured["timeout"] = timeout
        assert request.full_url.endswith(  # type: ignore[attr-defined]
            "/api/v1/internal/reservations/expire"
        )
        header_values = [
            value for _key, value in request.header_items()  # type: ignore[attr-defined]
        ]
        assert secret in header_values
        return _FakeResponse(
            200,
            json.dumps({"expired_reservations": 2, "cancelled_orders": 1}).encode(),
        )

    monkeypatch.setattr(job.urllib.request, "urlopen", fake_urlopen)
    with caplog.at_level(logging.INFO, logger="gema.expire_reservations"):
        code = job.run_once(api_origin="http://example.test", secret=secret)

    assert code == 0
    assert "expired=2" in caplog.text
    assert secret not in caplog.text


def test_run_once_http_error_does_not_log_secret(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    secret = "super-secret-value-do-not-leak"

    def fake_urlopen(request: object, timeout: float = 0) -> _FakeResponse:
        raise HTTPError(
            url="http://example.test/api/v1/internal/reservations/expire",
            code=401,
            msg="Unauthorized",
            hdrs=None,  # type: ignore[arg-type]
            fp=io.BytesIO(b'{"detail":"Invalid internal job secret"}'),
        )

    monkeypatch.setattr(job.urllib.request, "urlopen", fake_urlopen)
    with caplog.at_level(logging.ERROR, logger="gema.expire_reservations"):
        code = job.run_once(api_origin="http://example.test", secret=secret)

    assert code == 1
    assert "http=401" in caplog.text
    assert secret not in caplog.text


def test_run_once_unreachable(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(request: object, timeout: float = 0) -> _FakeResponse:
        raise URLError("connection refused")

    monkeypatch.setattr(job.urllib.request, "urlopen", fake_urlopen)
    assert job.run_once(api_origin="http://example.test", secret="x") == 1


def test_run_once_timeout_does_not_log_secret(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    secret = "timeout-secret-must-not-leak"

    def fake_urlopen(request: object, timeout: float = 0) -> _FakeResponse:
        raise TimeoutError("timed out")

    monkeypatch.setattr(job.urllib.request, "urlopen", fake_urlopen)
    with caplog.at_level(logging.ERROR, logger="gema.expire_reservations"):
        code = job.run_once(api_origin="http://example.test", secret=secret, timeout=0.5)

    assert code == 1
    assert "timeout" in caplog.text.lower()
    assert secret not in caplog.text


def test_main_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RESERVATION_EXPIRE_ENABLED", "false")
    assert job.main([]) == 0


def test_main_requires_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("INTERNAL_JOB_SECRET", raising=False)
    monkeypatch.setenv("RESERVATION_EXPIRE_ENABLED", "true")
    assert job.main([]) == 1
