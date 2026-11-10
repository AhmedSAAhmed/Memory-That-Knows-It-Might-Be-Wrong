import json
from datetime import datetime, timezone

import pytest

from app.agent.orchestrator import Agent
from app.memory.clock import ManualClock
from app.memory.store import MemoryStore
from app.memory.write_path import WritePath
from tests.test_extraction import FakeLLM, payload
from tests.test_memory import fact


@pytest.fixture
def scenario(tmp_path):
    clock = ManualClock(datetime(2026, 11, 10, tzinfo=timezone.utc))
    with MemoryStore(tmp_path / "test.db") as store:
        writer = WritePath(store, clock=clock)
        candidate = fact()
        memory_id = writer.write("a", "origin", candidate.quote, [candidate], guard_score=0.0).stored_ids[0]
        yield store, writer, clock, memory_id


def test_assertion_falls_back_to_grounded_reply_if_model_invents_citations(scenario):
    store, writer, clock, memory_id = scenario
    result = Agent(llm=FakeLLM(), writer=writer).respond("a", "Which delivery city?", [], incognito=True)
    assert result.used_ids == [memory_id]
    assert "Dubai" in result.reply and "invented" not in result.used_ids


def test_stale_answer_hedges_without_using_llm(scenario):
    store, writer, clock, memory_id = scenario
    clock.advance(days=365)
    llm = FakeLLM()
    result = Agent(llm=llm, writer=writer).respond("a", "Which city?", [], incognito=True)
    assert "I might be wrong" in result.reply and "Dubai" in result.reply
    assert result.hedged_ids == [memory_id]
    assert "answer" not in llm.calls


def test_too_old_answer_asks_without_revealing_value(scenario):
    store, writer, clock, memory_id = scenario
    clock.advance(days=730)
    llm = FakeLLM()
    result = Agent(llm=llm, writer=writer).respond("a", "Which city?", [], incognito=True)
    assert "Dubai" not in result.reply and "Dubai" not in json.dumps(result.evidence)
    assert "answer" not in llm.calls
    assert not result.used_ids


def test_actual_forgetting_clears_history_and_cannot_be_undone_by_chat_history(scenario):
    store, writer, clock, memory_id = scenario
    llm = FakeLLM(payload(candidates=[]))
    agent = Agent(llm=llm, writer=writer)
    result = agent.respond("a", "forget everything", [])
    assert result.clear_history and "forgot" in result.reply.casefold()
    assert not store.list_memories("a")
    captured = []
    original = llm.chat
    def capture(messages, **kwargs):
        captured.append(messages)
        return original(messages, **kwargs)
    llm.chat = capture
    agent.respond("a", "Which city?", [{"role": "user", "content": "I live in Dubai"}], incognito=True)
    assert "Dubai" not in json.dumps(captured)


def test_forget_one_does_not_forget_unrelated_key(scenario):
    store, writer, clock, memory_id = scenario
    candidate = fact("English", category="language", key="language", quote="I speak English")
    writer.write("a", "language", candidate.quote, [candidate], guard_score=0.0)
    result = Agent(llm=FakeLLM(), writer=writer).respond("a", "please forget my city", [])
    assert result.clear_history
    assert [(r.key, r.value) for r in store.list_memories("a")] == [("language", "English")]


def test_negative_forget_sentence_does_not_execute_deletion(scenario):
    store, writer, clock, memory_id = scenario
    Agent(llm=FakeLLM(payload(candidates=[])), writer=writer).respond("a", "Don't forget my city", [])
    assert store.get("a", memory_id).status == "active"


def test_memory_content_is_never_inserted_into_system_instructions(scenario):
    _, writer, _, _ = scenario
    llm = FakeLLM()
    captured = []
    original = llm.chat
    def capture(messages, **kwargs):
        captured.extend(messages)
        return original(messages, **kwargs)
    llm.chat = capture
    Agent(llm=llm, writer=writer).respond("a", "Which city?", [], incognito=True)
    assert "Dubai" not in " ".join(m["content"] for m in captured if m["role"] == "system")
    assert "Dubai" in " ".join(m["content"] for m in captured if m["role"] == "user")
