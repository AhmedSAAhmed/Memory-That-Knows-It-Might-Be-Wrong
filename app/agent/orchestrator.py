"""Turn orchestration: guard -> (write path) -> (retrieval) -> answer.

Day 1: screened extraction and persistent writes. Retrieval and forgetting
remain Day 2 work; the answer still receives an empty evidence pack.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from uuid import uuid4
from threading import RLock

from app.config import get_settings, memory_config, prompt
from app.llm.client import LLMClient, LLMUnavailable
from app.llm.extractor import ExtractionError, Extractor
from app.memory.privacy import message_reason, screening_reason
from app.memory.store import MemoryStore
from app.memory.write_path import WritePath
from app.agent.limits import RateLimiter

log = logging.getLogger(__name__)

@dataclass
class TurnResult:
    reply: str
    evidence: list[dict] = field(default_factory=list)
    used_ids: list[str] = field(default_factory=list)
    hedged_ids: list[str] = field(default_factory=list)
    injection_score: float | None = None
    provider: str = ""
    model: str = ""
    notes: list[str] = field(default_factory=list)
    written_ids: list[str] = field(default_factory=list)


class Agent:
    def __init__(self, llm: LLMClient | None = None, limiter: RateLimiter | None = None,
                 writer: WritePath | None = None) -> None:
        s = get_settings()
        self.llm = llm or LLMClient()
        self.limiter = limiter or RateLimiter(s.max_messages_per_session_per_hour)
        self._writer = writer
        self._database_path = s.database_path
        self._store_lock = RLock()
        self._owns_store = writer is None
        self.extractor = Extractor(self.llm)

    @property
    def writer(self) -> WritePath:
        with self._store_lock:
            if self._writer is None:
                self._writer = WritePath(MemoryStore(self._database_path))
            return self._writer

    def start(self) -> None:
        # Open/validate storage during app startup, rather than module import.
        self.writer

    def close(self) -> None:
        with self._store_lock:
            if self._owns_store and self._writer is not None:
                self._writer.store.close()
                self._writer = None

    def respond(self, session_id: str, message: str, history: list[dict], *,
                message_id: str | None = None, incognito: bool = False,
                allowed_orders: set[str] | None = None) -> TurnResult:
        message = (message or "").strip()
        if not message:
            return TurnResult(reply="")
        if not self.limiter.allow(session_id):
            return TurnResult(reply="You've reached the demo's hourly message limit. Please try again later.",
                              notes=["rate limited"])
        if len(message) > memory_config()["limits"]["message_chars"]:
            return TurnResult(reply="Please shorten your message before sending it.", notes=["message too long"])
        if message_reason(message) == "secret_detected":
            return TurnResult(reply="I won't keep passwords, payment details or identity documents. Please leave those out of chat.",
                              notes=["secret_detected: not sent to models or memory"])
        if re.search(r"\b(?:forget|revoke|erase)\b", message, flags=re.IGNORECASE):
            return TurnResult(reply="Forgetting is not available in this starter build yet. I haven't erased any memories.",
                              notes=["forgetting pending Day 2"])

        score = self.llm.injection_score(message)
        notes: list[str] = []
        blocked = screening_reason(score) or message_reason(message)
        written_ids: list[str] = []
        if incognito:
            notes.append("incognito: nothing written to memory")
        elif blocked:
            notes.append(f"prompt-guard: {blocked}; nothing written to memory")
        else:
            try:
                extracted = self.extractor.extract(message, guard_score=score)
                notes.extend(extracted.reasons)
                if not extracted.reasons:
                    written = self.writer.write(session_id, message_id or uuid4().hex, message, extracted.candidates,
                                                guard_score=score, allowed_orders=allowed_orders)
                    written_ids = written.stored_ids
                    notes.extend(written.reasons)
                    if written_ids:
                        notes.append(f"memory writes: {len(written_ids)}")
            except (ExtractionError, LLMUnavailable):
                notes.append("extraction unavailable: nothing written to memory")

        evidence: list[dict] = []  # Day 1-2: retrieval.build_evidence(customer_id, message)
        system = prompt("answerer") + "\n\nEVIDENCE:\n" + (json.dumps(evidence, ensure_ascii=False) or "[]")
        msgs = [{"role": "system", "content": system}]
        msgs += [{"role": m["role"], "content": str(m["content"])} for m in history[-10:]
                 if m.get("role") in ("user", "assistant") and message_reason(str(m.get("content", ""))) != "secret_detected"]
        msgs.append({"role": "user", "content": message})

        try:
            res = self.llm.chat(msgs, json_mode=True)
        except LLMUnavailable as exc:
            log.error("answer failed: %s", exc)
            return TurnResult(reply="Sorry, I can't reach my language model right now. Please try again in a minute.",
                              injection_score=score, notes=notes + ["llm unavailable"], written_ids=written_ids)

        data = _parse_json(res.text)
        return TurnResult(
            reply=str(data.get("reply") or res.text),
            evidence=evidence,
            used_ids=[],  # Day 2 will validate IDs against retrieved evidence.
            hedged_ids=[],
            injection_score=score,
            provider=res.provider,
            model=res.model,
            notes=notes,
            written_ids=written_ids,
        )


def _parse_json(text: str) -> dict:
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if 0 <= start < end:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                pass
        return {}
