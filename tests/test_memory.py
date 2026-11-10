"""Day 1 behavior contracts: offline, isolated SQLite, deterministic time."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.config import memory_config
from app.memory.clock import ManualClock
from app.memory.confidence import assess
from app.memory.models import Candidate
from app.memory.store import MemoryStore
from app.memory.write_path import WritePath


@pytest.fixture
def memory(tmp_path):
    clock = ManualClock(datetime(2026, 11, 10, tzinfo=timezone.utc))
    store = MemoryStore(tmp_path / "memory.db")
    yield store, WritePath(store, clock=clock), clock
    store.close()


def fact(value="Dubai", **changes):
    return Candidate(**{
        "category": "location", "key": "delivery_city", "value": value,
        "text": f"Customer lives in {value}.", "source": "user_stated",
        "quote": f"I live in {value}", "scope": "customer", **changes,
    })


def write(writer, candidate=None, *, customer="layla", event="m1", **kwargs):
    candidate = candidate or fact()
    kwargs.setdefault("guard_score", 0.0)
    return writer.write(customer, event, candidate.quote, [candidate], **kwargs)


def test_store_survives_reopen_and_preserves_provenance(memory):
    store, writer, clock = memory
    result = write(writer)
    assert len(result.stored_ids) == 1
    with MemoryStore(store.path) as reopened:
        record = reopened.get("layla", result.stored_ids[0])
        assert (record.value, record.quote, record.source_message_id) == ("Dubai", "I live in Dubai", "m1")
        assert record.base_confidence == memory_config()["source_base_confidence"]["user_stated"]
        assert record.created_at == record.last_confirmed_at == clock.now()
        assert reopened.get("other", record.id) is None


def test_newer_statement_supersedes_and_updates_search(memory):
    store, writer, clock = memory
    old_id = write(writer).stored_ids[0]
    clock.advance(days=1)
    new_id = write(writer, fact("Abu Dhabi"), event="m2").stored_ids[0]
    assert store.get("layla", old_id).status == "superseded"
    assert store.get("layla", new_id).supersedes == old_id
    assert [r.value for r in store.list_memories("layla")] == ["Abu Dhabi"]
    assert len(store.list_memories("layla", include_history=True)) == 2
    assert store.search("layla", "Dubai") == []
    assert [r.id for r in store.search("layla", "Abu")] == [new_id]


@pytest.mark.parametrize("source", ["inferred", "crm_import", "agent_record"])
def test_customer_statement_beats_other_sources_in_both_orders(memory, source):
    store, writer, clock = memory
    write(writer, fact("Dubai", source=source))
    clock.advance(days=1)
    write(writer, fact("Abu Dhabi"), event="m2")
    clock.advance(days=1)
    write(writer, fact("Sharjah", source=source), event="m3")
    assert [r.value for r in store.list_memories("layla")] == ["Abu Dhabi"]
    assert len(store.list_memories("layla", include_history=True)) == 3


def test_import_conflict_contested_then_customer_resolves_all(memory):
    store, writer, clock = memory
    write(writer, fact(source="inferred"))
    write(writer, fact("Abu Dhabi", source="crm_import"), event="m2")
    assert {r.status for r in store.list_memories("layla")} == {"contested"}
    assert all(assess(r, clock.now()).band == "ask" for r in store.list_memories("layla"))
    write(writer, fact("Sharjah"), event="m3")
    assert [(r.value, r.status) for r in store.list_memories("layla")] == [("Sharjah", "active")]


def test_out_of_order_and_equal_time_statements_do_not_guess(memory):
    store, writer, clock = memory
    write(writer)
    write(writer, fact("Abu Dhabi"), event="m2", occurred_at=clock.now() - timedelta(days=1))
    assert [r.value for r in store.list_memories("layla")] == ["Dubai"]
    write(writer, fact("Sharjah"), event="m3")
    assert {r.status for r in store.list_memories("layla")} == {"contested"}


def test_replay_is_idempotent_and_corroboration_is_capped(memory):
    store, writer, clock = memory
    memory_id = write(writer).stored_ids[0]
    clock.advance(days=1)
    for _ in range(3):
        write(writer)
    record = store.get("layla", memory_id)
    assert record.corroborations == 0
    assert record.last_confirmed_at < clock.now()
    for i in range(20):
        write(writer, event=f"repeat-{i}")
    record = store.get("layla", memory_id)
    assert record.corroborations == 20
    assert record.last_confirmed_at == clock.now()
    assert assess(record, clock.now()).effective == memory_config()["corroboration_cap"]


def test_weak_corroboration_does_not_refresh_customer_source(memory):
    store, writer, clock = memory
    memory_id = write(writer).stored_ids[0]
    clock.advance(days=300)
    write(writer, fact(source="inferred"), event="m2")
    record = store.get("layla", memory_id)
    assert record.source == "user_stated" and record.source_message_id == "m1"
    assert record.last_confirmed_at < clock.now()


def test_decay_bands_half_life_and_terminal_states(memory):
    store, writer, clock = memory
    record = store.get("layla", write(writer).stored_ids[0])
    assert assess(record, clock.now()).band == "assert"
    half_life = memory_config()["categories"]["location"]["half_life_days"]
    clock.advance(days=half_life)
    aged = assess(record, clock.now())
    assert aged.effective == pytest.approx(record.base_confidence / 2)
    assert aged.stale and aged.band == "hedge"
    clock.advance(days=half_life)
    assert assess(record, clock.now()).band == "ask"
    assert assess(replace(record, status="contested"), record.created_at).band == "ask"
    for status in ("revoked", "superseded"):
        assert assess(replace(record, status=status), record.created_at).effective == 0
    assert assess(record, record.created_at - timedelta(days=1)).effective == record.base_confidence


def test_scope_and_customer_isolation_in_sql_and_search(memory):
    store, writer, _ = memory
    write(writer)
    write(writer, fact("Sharjah"), customer="other")
    write(writer, fact("Abu Dhabi", scope="order:123"), event="m2", allowed_orders={"123"})
    assert [r.value for r in store.list_memories("layla")] == ["Dubai"]
    assert [r.value for r in store.list_memories("layla", scope="order:123")] == ["Abu Dhabi"]
    assert store.search("other", "Dubai") == []
    assert store.search("layla", "Abu") == []
    assert store.search("layla", '" OR * --') == []


@pytest.mark.parametrize("kwargs,reason", [
    ({"incognito": True}, "incognito"),
    ({"guard_score": None}, "screening_unavailable"),
    ({"guard_score": float("nan")}, "screening_unavailable"),
    ({"guard_score": 2}, "screening_unavailable"),
    ({"guard_score": 0.99}, "instruction_like"),
])
def test_write_fails_closed_without_valid_screening(memory, kwargs, reason):
    store, writer, _ = memory
    result = write(writer, **kwargs)
    assert reason in result.reasons
    assert store.list_memories("layla", include_history=True) == []


def test_persisted_privacy_settings_and_consent(memory):
    store, writer, _ = memory
    store.set_privacy("layla", blocked={"location"}, consented=set())
    assert "blocked_category" in write(writer).reasons
    health = fact("pregnant", category="health", key="health_note", quote="I am pregnant")
    assert "consent_required" in write(writer, health, event="h1").reasons
    store.set_privacy("layla", blocked=set(), consented={"health"})
    assert write(writer, health, event="h2").stored_ids
    with MemoryStore(store.path) as reopened:
        assert reopened.privacy("layla")[1] == {"health"}
    assert store.privacy("other") == (set(), set())


@pytest.mark.parametrize("message", [
    "I live in Dubai. My password is hunter2",
    "I live in Dubai. Card 4111 1111 1111 1111",
    "I live in Dubai. OTP: 123456",
    "I live in Dubai. IBAN AE070331234567890123456",
    "I live in Dubai. Passport number AB1234567",
])
def test_secret_in_message_never_reaches_facts_fts_or_audit(memory, message):
    store, writer, _ = memory
    result = writer.write("layla", "secret-event", message, [fact()], guard_score=0.0)
    assert "secret_detected" in result.reasons
    assert not store.list_memories("layla", include_history=True)
    assert not store.search("layla", "Dubai")
    assert all(message not in str(event) and "hunter2" not in str(event) for event in store.audit("layla"))


def test_mislabeled_sensitive_candidate_and_untrusted_scope_rejected(memory):
    store, writer, _ = memory
    disguised = fact("pregnant", quote="I am pregnant")
    assert "consent_required" in write(writer, disguised).reasons
    assert "unauthorized_scope" in write(writer, fact(scope="order:other"), event="m2").reasons
    assert "session_scope_not_persisted" in write(writer, fact(scope="session"), event="m3").reasons
    assert store.list_memories("layla") == []


def test_quote_must_come_from_actual_message(memory):
    store, writer, _ = memory
    result = writer.write("layla", "m1", "Hello there", [fact()], guard_score=0.0)
    assert "invalid_quote" in result.reasons
    assert store.list_memories("layla") == []


@pytest.mark.parametrize("changes", [
    {"category": "unknown"}, {"source": "system"}, {"key": "DROP TABLE"},
    {"scope": "workspace"}, {"value": ""}, {"value": 123}, {"quote": ""},
])
def test_candidate_validation(changes):
    with pytest.raises(ValueError):
        fact(**changes)


def test_transaction_rolls_back_facts_and_fts_if_audit_fails(memory, monkeypatch):
    store, writer, _ = memory
    def fail(*args, **kwargs):
        raise RuntimeError("simulated disk error")
    monkeypatch.setattr(store, "_audit", fail)
    with pytest.raises(RuntimeError):
        write(writer)
    assert store.list_memories("layla", include_history=True) == []
    assert store.search("layla", "Dubai") == []


def test_concurrent_replay_has_one_fact_and_one_event(memory):
    store, writer, _ = memory
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda _: write(writer), range(12)))
    records = store.list_memories("layla")
    assert len(records) == 1 and records[0].corroborations == 0
    assert len(store.audit("layla")) == 1


def test_clock_rejects_naive_datetimes():
    with pytest.raises(ValueError):
        ManualClock(datetime(2026, 1, 1))


def test_explicit_same_value_resolves_contested_group(memory):
    store, writer, clock = memory
    write(writer, fact(source="inferred"))
    write(writer, fact("Sharjah", source="crm_import"), event="m2")
    clock.advance(seconds=1)
    write(writer, event="m3")
    assert [(r.value, r.status, r.source) for r in store.list_memories("layla")] == [("Dubai", "active", "user_stated")]


def test_same_value_upgrades_source_even_at_equal_time(memory):
    store, writer, _ = memory
    write(writer, fact(source="inferred"))
    write(writer, event="m2")
    assert store.list_memories("layla")[0].source == "user_stated"


def test_ambiguous_batch_does_not_pick_first_candidate(memory):
    store, writer, _ = memory
    message = "I live in Dubai or Sharjah"
    result = writer.write("layla", "m1", message, [fact(quote=message), fact("Sharjah", quote=message)], guard_score=0.0)
    assert not result.stored_ids and "ambiguous_candidates" in result.reasons
    assert store.list_memories("layla") == []


@pytest.mark.parametrize("alias", ["home_city", "current_city", "city", "residence_city"])
def test_city_aliases_resolve_the_same_fact(memory, alias):
    store, writer, clock = memory
    write(writer)
    clock.advance(seconds=1)
    write(writer, fact("Abu Dhabi", key=alias), event="m2")
    assert [(r.key, r.value) for r in store.list_memories("layla")] == [("delivery_city", "Abu Dhabi")]


def test_concurrent_connections_preserve_idempotency(memory):
    store, _, clock = memory
    def event(_):
        with MemoryStore(store.path) as connection:
            write(WritePath(connection, clock=clock))
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(event, range(8)))
    assert len(store.list_memories("layla")) == 1
    assert store.list_memories("layla")[0].corroborations == 0


def test_batch_rollback_restores_superseded_fact_and_search(memory, monkeypatch):
    store, writer, clock = memory
    old_id = write(writer).stored_ids[0]
    clock.advance(seconds=1)
    audit = store._audit
    def fail_on_new(db, customer, action, at, **kwargs):
        if action == "written":
            raise RuntimeError("simulated failure after supersede")
        audit(db, customer, action, at, **kwargs)
    monkeypatch.setattr(store, "_audit", fail_on_new)
    with pytest.raises(RuntimeError):
        write(writer, fact("Abu Dhabi"), event="m2")
    assert store.get("layla", old_id).status == "active"
    assert [r.id for r in store.search("layla", "Dubai")] == [old_id]
    assert store.search("layla", "Abu") == []


def test_category_cannot_change_to_evade_privacy_or_decay(memory):
    store, writer, _ = memory
    write(writer)
    result = write(writer, fact(category="identity"), event="m2")
    assert "category_mismatch" in result.reasons
    assert store.list_memories("layla")[0].category == "location"


def test_future_source_timestamp_rejected(memory):
    store, writer, clock = memory
    with pytest.raises(ValueError):
        write(writer, occurred_at=clock.now() + timedelta(days=1))
    assert store.list_memories("layla") == []


def test_new_customer_statement_refreshes_previous_confirmation(memory):
    store, writer, clock = memory
    memory_id = write(writer, fact(source="user_confirmed")).stored_ids[0]
    clock.advance(days=400)
    write(writer, event="new-statement")
    record = store.get("layla", memory_id)
    assert record.last_confirmed_at == clock.now()
    assert record.source_message_id == "new-statement"
    assert assess(record, clock.now()).band == "assert"


def test_corroboration_also_decays(memory):
    store, writer, clock = memory
    memory_id = write(writer).stored_ids[0]
    for i in range(20):
        write(writer, event=f"e-{i}")
    record = store.get("layla", memory_id)
    clock.advance(days=365)
    assert assess(record, clock.now()).effective == pytest.approx(memory_config()["corroboration_cap"] / 2)
