"""Turn orchestration: guard -> (write path) -> (retrieval) -> answer.

Memory is evidence, never instructions. Low-confidence responses are enforced
in code; chat history cannot resurrect erased facts.
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
from app.memory.forgetting import Forgetting
from app.memory.retrieval import Retriever
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
    clear_history: bool = False


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
        Forgetting(self.writer.store, clock=self.writer.clock).sweep()

    def close(self) -> None:
        with self._store_lock:
            if self._owns_store and self._writer is not None:
                self._writer.store.close()
                self._writer = None

    def respond(self, session_id: str, message: str, history: list[dict], *,
                message_id: str | None = None, incognito: bool = False,
                allowed_orders: set[str] | None = None, clock=None, session_store=None) -> TurnResult:
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
        writer = self.writer if clock is None else WritePath(self.writer.store, clock=clock)
        forgetting = Forgetting(writer.store, clock=writer.clock)
        forgetting.sweep(session_id)
        stores = [writer.store] + ([session_store] if session_store is not None else [])
        command = re.match(r"^(?:please\s+)?(?:forget|revoke|erase)\s+(.+?)[.!]?$", message, flags=re.IGNORECASE)
        if command:
            target = command[1].casefold().strip()
            if target in {"everything", "all", "all memories", "all my memories"}:
                count = sum(Forgetting(store, clock=writer.clock).forget_all(session_id) for store in stores)
            else:
                words = set(re.findall(r"\w+", target)) - {"my", "the", "about", "me"}
                count = 0
                for store in stores:
                    records = store.all_memories(session_id, include_history=False)
                    ids = {r.id for r in records if words & set(r.key.split("_")) or r.value.casefold() == target}
                    count += sum(Forgetting(store, clock=writer.clock).revoke(session_id, memory_id) for memory_id in ids)
            reply = "I forgot the matching memories and erased their stored content." if count else "No stored memories matched that request. You can select a fact in the memory inspector."
            return TurnResult(reply=reply, clear_history=True, notes=[f"revoked keys: {count}"])
        privacy_command = re.fullmatch(r"never remember\s+([a-z_]+)[.!]?", message, flags=re.IGNORECASE)
        if privacy_command and privacy_command[1].lower() in memory_config()["categories"]:
            category = privacy_command[1].lower()
            blocked_categories, consented = writer.store.privacy(session_id)
            for store in stores:
                store.set_privacy(session_id, blocked=blocked_categories | {category}, consented=consented - {category})
            return TurnResult(reply=f"I won't remember new facts in the {category} category.")

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
                    source_event = message_id or uuid4().hex
                    durable = [candidate for candidate in extracted.candidates if candidate.scope != "session"]
                    transient = [candidate for candidate in extracted.candidates if candidate.scope == "session"]
                    written = writer.write(session_id, source_event, message, durable,
                                                guard_score=score, allowed_orders=allowed_orders)
                    written_ids = written.stored_ids
                    notes.extend(written.reasons)
                    if transient and session_store is not None:
                        temporary = WritePath(session_store, clock=writer.clock, allow_session=True).write(
                            session_id, source_event, message, transient, guard_score=score)
                        written_ids.extend(temporary.stored_ids)
                        notes.extend(temporary.reasons)
                    if written_ids:
                        notes.append(f"memory writes: {len(written_ids)}")
                        embedder = getattr(self.llm, "embed", None)
                        if embedder:
                            for memory_id in written_ids:
                                target_store = next((store for store in stores if store.get(session_id, memory_id)), writer.store)
                                record = target_store.get(session_id, memory_id)
                                if record and record.status in {"active", "stale"}:
                                    try:
                                        vector = embedder(record.text)
                                        if vector:
                                            target_store.put_embedding(session_id, memory_id, vector, expected_text=record.text)
                                    except Exception:
                                        notes.append("embedding unavailable: lexical search remains active")
            except (ExtractionError, LLMUnavailable):
                notes.append("extraction unavailable: nothing written to memory")

        scopes = ("customer",) + tuple("order:" + order for order in sorted(allowed_orders or set()))
        evidence = [] if blocked else Retriever(writer.store, clock=writer.clock, embedder=getattr(self.llm, "embed", None)).retrieve(session_id, message, scopes=scopes)
        if session_store is not None and not blocked:
            Forgetting(session_store, clock=writer.clock).sweep(session_id)
            evidence.extend(Retriever(session_store, clock=writer.clock).retrieve(session_id, message, scopes=("session",)))
        common = dict(evidence=evidence, injection_score=score, notes=notes, written_ids=written_ids)
        uncertain = [item for item in evidence if item["band"] == "ask"]
        hedged = [item for item in evidence if item["band"] == "hedge"]
        if uncertain:
            keys = ", ".join(dict.fromkeys(item["key"].replace("_", " ") for item in uncertain))
            return TurnResult(reply=f"I might be wrong about this. Could you confirm your {keys}?", **common)
        if hedged:
            facts = "; ".join(f"{item['key'].replace('_', ' ')} = {item['value']}" for item in hedged)
            return TurnResult(reply=f"I might be wrong about this: {facts}. Is that still correct?",
                              hedged_ids=[item["id"] for item in hedged], **common)
        system = prompt("answerer")
        msgs = [{"role": "system", "content": system}]
        # Raw prior turns are deliberately excluded: they can contain revoked,
        # superseded or low-confidence facts and bypass the evidence boundary.
        msgs.append({"role": "user", "content": json.dumps({"EVIDENCE": evidence, "question": message}, ensure_ascii=False)})

        try:
            res = self.llm.chat(msgs, json_mode=True)
        except LLMUnavailable as exc:
            log.error("answer failed (%s)", type(exc).__name__)
            if evidence:
                return TurnResult(reply=_grounded_reply(evidence), used_ids=[item["id"] for item in evidence], **common)
            return TurnResult(reply="Sorry, I can't reach my language model right now. Please try again in a minute.",
                              injection_score=score, notes=notes + ["llm unavailable"], written_ids=written_ids)

        data = _parse_json(res.text)
        ids = {item["id"] for item in evidence}
        used = data.get("used_ids", [])
        reply = data.get("reply")
        valid = isinstance(reply, str) and bool(reply.strip()) and isinstance(used, list) and all(isinstance(x, str) and x in ids for x in used)
        if evidence and (not valid or not used):
            reply = _grounded_reply(evidence)
            used = list(ids)
            notes.append("reply grounded in validated evidence")
        elif not valid:
            reply = "Could you clarify what you need help with?"
            used = []
        return TurnResult(
            reply=reply,
            evidence=evidence,
            used_ids=list(dict.fromkeys(used)),
            hedged_ids=[],
            injection_score=score,
            provider=res.provider,
            model=res.model,
            notes=notes,
            written_ids=written_ids,
        )


def _grounded_reply(evidence: list[dict]) -> str:
    return "; ".join(f"Your {item['key'].replace('_', ' ')} is {item['value']} (source: {item['source']})." for item in evidence if item["band"] == "assert")


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
