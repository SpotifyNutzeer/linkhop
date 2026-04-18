from fastapi.testclient import TestClient

from linkhop.config import Settings
from linkhop.main import create_app


def test_health_returns_200_when_dependencies_ok(monkeypatch):
    monkeypatch.setenv("LINKHOP_REDIS_URL", "redis://localhost:6379/0")
    app = create_app(Settings())
    with TestClient(app) as client:
        resp = client.get("/api/v1/health")
    # Tolerant — echte Redis/Postgres laufen im Test nicht
    assert resp.status_code in (200, 503)
    body = resp.json()
    assert body["status"] in ("ok", "degraded")
    assert "redis" in body
    assert "postgres" in body
