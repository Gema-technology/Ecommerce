from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_check() -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "gema-api"}


def test_readiness_check_reports_dependencies() -> None:
    response = client.get("/api/v1/health/ready")
    assert response.status_code in {200, 503}
    body = response.json()
    assert body["service"] == "gema-api"
    assert "postgres" in body["checks"]
    assert "redis" in body["checks"]
    if response.status_code == 200:
        assert body["status"] == "ok"
        assert body["checks"]["postgres"] == "ok"
    else:
        assert body["status"] == "unavailable"
