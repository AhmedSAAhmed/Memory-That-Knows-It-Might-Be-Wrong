from dataclasses import replace
import json

import pytest
from fastapi.testclient import TestClient

from app.agent.orchestrator import Agent
from app.service import MemoryService
from app.sessions import SessionIdentity
from app.memory.store import MemoryStore
from app.memory.write_path import WritePath
from tests.test_extraction import FakeLLM
from tests.test_memory import fact


@pytest.fixture
def service(tmp_path):
    with MemoryStore(tmp_path / "api.db") as store:
        service = MemoryService(Agent(llm=FakeLLM(), writer=WritePath(store)), seed_demo=False)
        yield service
        service.close()


def test_signed_identity_rejects_tampering_and_expiry():
    t = [10.0]
    identity = SessionIdentity(secret=b"test-key", timer=lambda: t[0])
    token = identity.issue()
    assert identity.verify(token)
    assert identity.verify("forged." + token.split(".", 1)[1]) is None
    t[0] += 100000
    assert identity.verify(token) is None


def test_service_clock_and_privacy_are_customer_scoped(service):
    service.set_days("a", 365)
    assert service.clock("a").offset_days == 365
    assert service.clock("b").offset_days == 0
    service.set_privacy("a", {"location"}, {"health"})
    assert service.store.privacy("b") == (set(), set())
    with pytest.raises(ValueError):
        service.set_days("a", 0)


def test_inspector_confirm_correct_revoke_and_export(service):
    candidate = fact()
    first = service.writer("a").write("a", "first", candidate.quote, [candidate], guard_score=0.0).stored_ids[0]
    service.confirm("a", first)
    assert service.store.get("a", first).source == "user_confirmed"
    service.correct("a", first, "Abu Dhabi")
    active = service.store.list_memories("a")
    assert len(active) == 1 and active[0].value == "Abu Dhabi"
    assert "Dubai" in json.dumps(service.history("a", active[0].id))
    assert service.revoke("a", active[0].id)
    assert "Dubai" not in json.dumps(service.export("a"))
    with pytest.raises(KeyError):
        service.confirm("b", first)


def test_seed_and_reset_do_not_resurrect_forgotten_facts(service):
    service.seed_demo = True
    original = service.snapshot("a")
    assert original
    assert service.forget_all("a") > 0
    assert not [r for r in service.snapshot("a") if r["status"] != "revoked"]
    assert service.reset("a")
    assert [r for r in service.snapshot("a") if r["status"] == "active"]


def test_api_cookies_isolate_customers_and_reject_spoofed_identity(service, monkeypatch):
    import app.main as main
    monkeypatch.setattr(main, "service", service)
    with TestClient(main.app) as one, TestClient(main.app) as two:
        assert one.get("/api/memories").status_code == 200
        token = one.cookies.get("memory_session")
        customer = main.identities.verify(token)
        candidate = fact()
        memory_id = service.writer(customer).write(customer, "first", candidate.quote, [candidate], guard_score=0.0).stored_ids[0]
        assert "Dubai" in one.get("/api/memories").text
        assert "Dubai" not in two.get("/api/memories", params={"customer_id": customer}).text
        assert two.post(f"/api/memories/{memory_id}/revoke").status_code == 404
        assert one.get("/api/memories/export").headers["content-type"].startswith("application/json")
        assert one.post(f"/api/memories/{memory_id}/revoke").status_code == 200
        assert "Dubai" not in one.get("/api/memories/export").text


def test_session_memories_never_enter_disk_and_expire_with_service(service):
    candidate = fact(scope="session")
    result = service.respond("a", candidate.quote, [], incognito=False)
    # Explicit session candidates use a separate in-memory store.
    service.write_session("a", "temporary", candidate)
    assert service.session_store.list_memories("a", scope="session")
    assert not [r for r in service.store.all_memories("a") if r.scope == "session"]
    service.close()
    assert not service.session_store.list_memories("a", scope="session")


def test_customer_can_reconfirm_a_hedged_fact_without_resending_history(service):
    candidate = fact()
    memory_id = service.writer("a").write("a", "original", candidate.quote, [candidate], guard_score=0.0).stored_ids[0]
    service.set_days("a", 365)
    hedged = service.respond("a", "Which city?", [])
    assert hedged.hedged_ids == [memory_id]
    confirmed = service.respond("a", "yes", [])
    assert "confirmed" in confirmed.reply.casefold()
    assert service.store.get("a", memory_id).source == "user_confirmed"
    assert next(row for row in service.snapshot("a") if row["id"]==memory_id)["band"] == "assert"


def test_incognito_yes_does_not_refresh_a_hedged_fact(service):
    candidate = fact()
    memory_id = service.writer("a").write("a", "original", candidate.quote, [candidate], guard_score=0.0).stored_ids[0]
    service.set_days("a", 365)
    service.respond("a", "Which city?", [], incognito=True)
    service.respond("a", "yes", [], incognito=True)
    assert service.store.get("a", memory_id).source == "user_stated"


def test_forgetting_clears_pending_confirmation(service):
    candidate = fact()
    memory_id = service.writer("a").write("a", "original", candidate.quote, [candidate], guard_score=0.0).stored_ids[0]
    service.set_days("a", 365)
    service.respond("a", "Which city?", [])
    service.revoke("a", memory_id)
    service.respond("a", "yes", [])
    assert service.store.get("a", memory_id).status == "revoked"
    assert not service.store.get("a", memory_id).value


def test_reconfirmation_obeys_hourly_rate_limit(service):
    from app.agent.limits import RateLimiter
    candidate = fact()
    memory_id = service.writer("a").write("a", "original", candidate.quote, [candidate], guard_score=0.0).stored_ids[0]
    service.set_days("a", 365)
    service.agent.limiter = RateLimiter(1)
    service.respond("a", "Which city?", [])
    response = service.respond("a", "yes", [])
    assert "rate limited" in response.notes
    assert service.store.get("a", memory_id).source == "user_stated"
