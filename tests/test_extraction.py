"""Validate untrusted extraction output and the real agent write integration."""
import json
from dataclasses import replace
from types import SimpleNamespace

import pytest

from app.agent.orchestrator import Agent
from app.llm.client import LLMUnavailable
from app.llm.extractor import ExtractionError, Extractor
from app.memory.store import MemoryStore
from app.memory.write_path import WritePath


def payload(**changes):
    return {"candidates": [{"category": "location", "key": "delivery_city", "value": "Dubai",
                            "text": "Customer lives in Dubai.", "source": "user_stated",
                            "quote": "I live in Dubai", "scope": "customer"}],
            "secret_detected": False, "instruction_like": False, **changes}


class FakeLLM:
    def __init__(self, extraction=None, score=0.0):
        self.extraction = payload() if extraction is None else extraction
        self.score = score
        self.calls = []

    def injection_score(self, message):
        self.calls.append("guard")
        return self.score

    def chat(self, messages, **kwargs):
        fast = kwargs.get("fast", False)
        self.calls.append("extract" if fast else "answer")
        if fast and isinstance(self.extraction, Exception):
            raise self.extraction
        text = (self.extraction if isinstance(self.extraction, str) else json.dumps(self.extraction)) if fast else '{"reply":"Hello","used_ids":["invented"],"hedged_ids":[]}'
        return SimpleNamespace(text=text,
                               provider="fake", model="extract" if fast else "answer")


def test_extractor_uses_fast_model_and_validates_quote():
    llm = FakeLLM()
    result = Extractor(llm).extract("I live in Dubai", guard_score=0.0)
    assert result.candidates[0].key == "delivery_city"
    assert llm.calls == ["extract"]


@pytest.mark.parametrize("output", [
    "not json", "[]", '{"candidates":null}',
    payload(candidates="Dubai"), payload(secret_detected="false"),
    payload(candidates=[{**payload()["candidates"][0], "source": "user_confirmed"}]),
    payload(candidates=[{**payload()["candidates"][0], "quote": "not in message"}]),
    payload(candidates=[{**payload()["candidates"][0], "customer_id": "other"}]),
    payload(candidates=[{**payload()["candidates"][0], "scope": "workspace"}]),
    payload(candidates=[payload()["candidates"][0], {**payload()["candidates"][0], "value": "Sharjah"}]),
])
def test_invalid_extraction_rejected_as_a_whole(output):
    with pytest.raises(ExtractionError):
        Extractor(FakeLLM(output)).extract("I live in Dubai", guard_score=0.0)


@pytest.mark.parametrize("changes,reason", [
    ({"secret_detected": True}, "secret_detected"),
    ({"instruction_like": True}, "instruction_like"),
])
def test_extractor_flags_discard_all_candidates(changes, reason):
    result = Extractor(FakeLLM(payload(**changes))).extract("I live in Dubai", guard_score=0.0)
    assert not result.candidates and reason in result.reasons


@pytest.mark.parametrize("message,score", [("I live in Dubai", None), ("I live in Dubai", .99), ("My password is secret", 0.0)])
def test_extraction_never_calls_provider_without_privacy_and_screening(message, score):
    llm = FakeLLM()
    result = Extractor(llm).extract(message, guard_score=score)
    assert not result.candidates and result.reasons
    assert not llm.calls


def test_agent_writes_after_guard_before_answer_and_replay_is_safe(tmp_path):
    llm = FakeLLM()
    with MemoryStore(tmp_path / "test.db") as store:
        agent = Agent(llm=llm, writer=WritePath(store))
        result = agent.respond("layla", "I live in Dubai", [], message_id="event-1")
        assert llm.calls == ["guard", "extract", "answer"]
        assert result.written_ids == [store.list_memories("layla")[0].id]
        assert "invented" not in result.used_ids
        agent.respond("layla", "I live in Dubai", [], message_id="event-1")
        assert store.list_memories("layla")[0].corroborations == 0
        assert store.list_memories("someone-else") == []


@pytest.mark.parametrize("mode", ["incognito", "guard_down", "injection", "malformed", "provider_down"])
def test_agent_write_failures_leave_store_empty_but_answer_still_works(tmp_path, mode):
    llm = FakeLLM()
    if mode == "guard_down":
        llm.score = None
    if mode == "injection":
        llm.score = .99
    if mode == "malformed":
        llm.extraction = "not JSON"
    if mode == "provider_down":
        llm.extraction = LLMUnavailable("offline")
    with MemoryStore(tmp_path / "test.db") as store:
        result = Agent(llm=llm, writer=WritePath(store)).respond("layla", "I live in Dubai", [], incognito=mode == "incognito")
        assert result.reply and not result.used_ids
        assert not result.written_ids and not store.list_memories("layla", include_history=True)
        assert result.notes
        if mode in {"incognito", "guard_down", "injection"}:
            assert "extract" not in llm.calls


def test_agent_does_not_forward_secret_to_models(tmp_path):
    llm = FakeLLM()
    with MemoryStore(tmp_path / "test.db") as store:
        result = Agent(llm=llm, writer=WritePath(store)).respond("layla", "My password is hunter2", [])
        assert not llm.calls and not result.written_ids
        assert "won't keep" in result.reply


def test_model_cannot_claim_deletion_was_performed(tmp_path):
    llm = FakeLLM(payload(candidates=[]))
    with MemoryStore(tmp_path / "test.db") as store:
        result = Agent(llm=llm, writer=WritePath(store)).respond("layla", "Forget everything", [])
        assert "no stored memories" in result.reply.casefold()
        assert not llm.calls


def test_owned_store_opens_lazily_and_reopens_after_shutdown(tmp_path, monkeypatch):
    from app.config import get_settings
    path = tmp_path / "lifecycle.db"
    settings = replace(get_settings(), database_path=path)
    monkeypatch.setattr("app.agent.orchestrator.get_settings", lambda: settings)
    agent = Agent(llm=FakeLLM())
    assert not path.exists()
    agent.respond("layla", "I live in Dubai", [])
    first_store = agent.writer.store
    agent.close()
    assert agent.writer.store is not first_store
    assert len(agent.writer.store.list_memories("layla")) == 1
    agent.close()


def test_agent_shutdown_does_not_close_injected_store(tmp_path):
    with MemoryStore(tmp_path / "external.db") as store:
        agent = Agent(llm=FakeLLM(), writer=WritePath(store))
        agent.close()
        assert store.list_memories("layla") == []
