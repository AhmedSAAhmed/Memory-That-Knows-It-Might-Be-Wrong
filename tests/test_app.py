from fastapi.testclient import TestClient

from app.main import app


def test_health_ok():
    r = TestClient(app).get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert isinstance(body["llm_providers"], list)


def test_ui_served_at_root():
    r = TestClient(app).get("/")
    assert r.status_code == 200
    assert "<html" in r.text.lower()
