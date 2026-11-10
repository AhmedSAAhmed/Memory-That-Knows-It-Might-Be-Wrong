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


def test_health_identifies_deployed_revision(monkeypatch):
    monkeypatch.setenv("RENDER_GIT_COMMIT", "test-revision")
    assert TestClient(app).get("/health").json()["revision"] == "test-revision"


def test_app_lifespan_closes_storage_and_can_restart(tmp_path, monkeypatch):
    from dataclasses import replace
    import sqlite3
    import pytest
    import app.main as main
    from app.agent.orchestrator import Agent
    from app.config import get_settings

    settings = replace(get_settings(), database_path=tmp_path / "app.db")
    monkeypatch.setattr("app.agent.orchestrator.get_settings", lambda: settings)
    isolated_agent = Agent()
    monkeypatch.setattr(main, "agent", isolated_agent)
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        connection = isolated_agent.writer.store
        assert connection.list_memories("layla") == []
    with pytest.raises(sqlite3.ProgrammingError):
        connection.list_memories("layla")
    with TestClient(app) as client:
        assert client.get("/").status_code == 200
        assert isolated_agent.writer.store.list_memories("layla") == []
