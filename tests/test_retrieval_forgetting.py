"""Retrieval and erasure contracts, written before the Stage 03 implementation."""
from datetime import datetime, timezone
import json

import pytest

from app.memory.clock import ManualClock
from app.memory.forgetting import Forgetting
from app.memory.retrieval import Retriever
from app.memory.store import MemoryStore
from app.memory.write_path import WritePath
from tests.test_memory import fact


@pytest.fixture
def system(tmp_path):
    clock = ManualClock(datetime(2026, 11, 10, tzinfo=timezone.utc))
    with MemoryStore(tmp_path / "test.db") as store:
        yield store, WritePath(store, clock=clock), clock


def put(writer, candidate=None, customer="a", event="event"):
    candidate = candidate or fact()
    return writer.write(customer, event, candidate.quote, [candidate], guard_score=0.0).stored_ids[0]


def test_retrieval_cites_source_and_respects_scope(system):
    store, writer, clock = system
    memory_id = put(writer)
    put(writer, fact("Sharjah"), customer="b")
    evidence = Retriever(store, clock=clock).retrieve("a", "Which city do you deliver to?")
    assert len(evidence) == 1
    assert evidence[0]["id"] == memory_id
    assert evidence[0]["quote"] == "I live in Dubai"
    assert evidence[0]["band"] == "assert" and evidence[0]["value"] == "Dubai"
    assert "Sharjah" not in json.dumps(evidence)
    assert Retriever(store, clock=clock).retrieve("a", "my refund") == []


def test_sweep_is_idempotent_and_low_confidence_is_redacted(system):
    store, writer, clock = system
    memory_id = put(writer)
    clock.advance(days=365)
    forgetting = Forgetting(store, clock=clock)
    assert forgetting.sweep("a") == 1
    assert forgetting.sweep("a") == 0
    assert store.get("a", memory_id).status == "stale"
    evidence = Retriever(store, clock=clock).retrieve("a", "delivery city")
    assert evidence[0]["band"] == "hedge"
    clock.advance(days=365)
    evidence = Retriever(store, clock=clock).retrieve("a", "delivery city")
    assert evidence[0]["band"] == "ask"
    assert "Dubai" not in json.dumps(evidence)
    assert "quote" not in evidence[0] and "value" not in evidence[0]


def test_contested_values_never_enter_evidence(system):
    store, writer, clock = system
    put(writer, fact(source="inferred"))
    put(writer, fact("Sharjah", source="crm_import"), event="other")
    evidence = Retriever(store, clock=clock).retrieve("a", "delivery city")
    assert evidence and all(e["band"] == "ask" for e in evidence)
    assert "Dubai" not in json.dumps(evidence) and "Sharjah" not in json.dumps(evidence)


def test_revoke_erases_all_versions_indexes_vectors_and_quotes(system):
    store, writer, clock = system
    first = put(writer)
    store.put_embedding("a", first, [1.0, 0.0])
    clock.advance(seconds=1)
    second = put(writer, fact("Abu Dhabi"), event="new")
    store.put_embedding("a", second, [0.0, 1.0])
    assert not Forgetting(store, clock=clock).revoke("b", second)
    assert Forgetting(store, clock=clock).revoke("a", second)
    for record in store.list_memories("a", include_history=True):
        assert record.status == "revoked"
        assert not record.value and not record.quote and not record.text
    assert store.embeddings("a") == {}
    assert store.search("a", "Dubai") == []
    assert Retriever(store, clock=clock).retrieve("a", "city") == []
    with store.transaction() as db:
        dump = "\n".join(db.iterdump())
    assert "Dubai" not in dump and "Abu Dhabi" not in dump


def test_tombstone_blocks_old_events_and_imports_but_allows_fresh_statement(system):
    store, writer, clock = system
    old_time = clock.now()
    memory_id = put(writer)
    Forgetting(store, clock=clock).revoke("a", memory_id)
    clock.advance(seconds=1)
    for source, at in (("crm_import", clock.now()), ("inferred", clock.now()), ("user_stated", old_time)):
        candidate = fact(source=source)
        result = writer.write("a", "replay-" + source, candidate.quote, [candidate], guard_score=0.0, occurred_at=at)
        assert not result.stored_ids
    new_id = put(writer, event="new-statement")
    assert store.get("a", new_id).value == "Dubai"
    result = writer.write("a", "event", "I live in Dubai", [fact()], guard_score=0.0)
    assert not result.stored_ids


def test_forget_all_is_customer_scoped_and_all_scopes(system):
    store, writer, clock = system
    put(writer)
    order = fact("Al Ain", scope="order:42")
    writer.write("a", "order", order.quote, [order], guard_score=0.0, allowed_orders={"42"})
    put(writer, customer="b")
    assert Forgetting(store, clock=clock).forget_all("a") == 2
    assert not store.list_memories("a") and not store.list_memories("a", scope="order:42")
    assert len(store.list_memories("b")) == 1


def test_embedding_search_and_failure_fallback(system):
    store, writer, clock = system
    memory_id = put(writer)
    store.put_embedding("a", memory_id, [1.0, 0.0])
    evidence = Retriever(store, clock=clock, embedder=lambda _: [1.0, 0.0]).retrieve("a", "whereabouts")
    assert evidence[0]["id"] == memory_id
    def down(_):
        raise RuntimeError("provider down")
    assert Retriever(store, clock=clock, embedder=down).retrieve("a", "delivery city")[0]["id"] == memory_id


def test_revoked_fact_cannot_receive_a_late_embedding(system):
    store, writer, clock = system
    memory_id = put(writer)
    Forgetting(store, clock=clock).revoke("a", memory_id)
    assert not store.put_embedding("a", memory_id, [1.0, 0.0])
    assert not store.put_embedding("b", memory_id, [1.0, 0.0])
    assert store.embeddings("a") == {}


def test_read_audit_contains_ids_not_payloads(system):
    store, writer, clock = system
    put(writer)
    Retriever(store, clock=clock).retrieve("a", "city")
    events = store.audit("a")
    assert any(e["action"] == "read_for_answer" for e in events)
    assert "Dubai" not in json.dumps(events)
