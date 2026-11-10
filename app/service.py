"""Identity-bound product operations used by both the UI and HTTP API."""
from dataclasses import asdict
import json
from threading import RLock
import time
from uuid import uuid4

from app.config import SHARED, memory_config
from app.memory.clock import OffsetClock
from app.memory.confidence import assess
from app.memory.forgetting import Forgetting
from app.memory.models import Candidate
from app.memory.store import MemoryStore
from app.memory.write_path import WritePath


class MemoryService:
    def __init__(self, agent, *, seed_demo=True):
        self.agent = agent
        self.seed_demo = seed_demo
        self._clocks = {}
        self._last_seen = {}
        self._pending = {}
        self._session_store = None
        self._lock = RLock()

    @property
    def store(self):
        return self.agent.writer.store

    @property
    def session_store(self):
        with self._lock:
            if self._session_store is None:
                self._session_store = MemoryStore()
            return self._session_store

    def close(self):
        with self._lock:
            if self._session_store is not None:
                self._session_store.close()
                self._session_store = None
            self._clocks.clear()
            self._last_seen.clear()
            self._pending.clear()

    def clock(self, customer):
        with self._lock:
            now = time.monotonic()
            expired = [key for key,at in self._last_seen.items() if now-at >= memory_config()["demo"]["session_seconds"]]
            if customer not in self._clocks and len(self._clocks) >= memory_config()["demo"]["max_sessions"]:
                expired.append(min(self._last_seen, key=self._last_seen.get))
            for key in set(expired):
                self._clocks.pop(key, None)
                self._last_seen.pop(key, None)
                self._pending.pop(key, None)
                if self._session_store is not None:
                    self._session_store.clear_customer(key)
            self._last_seen[customer] = now
            return self._clocks.setdefault(customer, OffsetClock())

    def writer(self, customer):
        return WritePath(self.store, clock=self.clock(customer))

    def initialize(self, customer):
        with self._lock:
            if self.seed_demo and not self.store.all_memories(customer):
                candidates = json.loads((SHARED / "demo-memories.json").read_text(encoding="utf-8"))
                for item in candidates:
                    candidate = Candidate(**item)
                    self.writer(customer).write(customer, "seed:" + candidate.key, candidate.quote, [candidate], guard_score=0.0, allowed_orders={"QH1042"})

    def snapshot(self, customer):
        self.initialize(customer)
        now = self.clock(customer).now()
        records = []
        for store in (self.store, self.session_store):
            Forgetting(store, clock=self.clock(customer)).sweep(customer)
            for record in store.all_memories(customer):
                data = asdict(record)
                for key in ("created_at", "last_confirmed_at", "event_at"):
                    data[key] = data[key].isoformat()
                data["confidence"] = assess(record, now).effective
                data["band"] = assess(record, now).band
                records.append(data)
        return records

    def set_days(self, customer, days):
        if isinstance(days, bool) or not isinstance(days, (int,float)) or not 0 <= days <= memory_config()["demo"]["max_days"]:
            raise ValueError("Clock offset is outside the demo range")
        clock = self.clock(customer)
        if days < clock.offset_days:
            raise ValueError("Use Reset demo before turning the clock backwards")
        clock.offset_days = days
        for store in (self.store, self.session_store):
            Forgetting(store, clock=clock).sweep(customer)

    def set_privacy(self, customer, blocked, consented):
        self.store.set_privacy(customer, blocked=set(blocked), consented=set(consented))
        self.session_store.set_privacy(customer, blocked=set(blocked), consented=set(consented))

    def _record(self, customer, memory_id):
        for store in (self.store, self.session_store):
            record = store.get(customer, memory_id)
            if record:
                return store, record
        raise KeyError("Memory not found in this session")

    def confirm(self, customer, memory_id):
        store, record = self._record(customer, memory_id)
        if record.status in {"revoked", "superseded"}:
            raise ValueError("Select a current memory to confirm")
        candidate = Candidate(record.category, record.key, record.value, record.text, "user_confirmed", record.quote, record.scope)
        result = WritePath(store, clock=self.clock(customer), allow_session=store is self.session_store).write(
            customer, uuid4().hex, candidate.quote, [candidate], guard_score=0.0, allowed_orders={"QH1042"})
        if result.reasons:
            raise ValueError(", ".join(result.reasons))

    def correct(self, customer, memory_id, value):
        self._pending.pop(customer, None)
        store, record = self._record(customer, memory_id)
        if record.status == "revoked":
            raise ValueError("Restate a forgotten fact in chat to remember it again")
        candidate = Candidate(record.category, record.key, value, f"Customer's {record.key} is {value}.", "user_stated", value, record.scope)
        if not self.agent.limiter.allow(customer):
            raise ValueError("Hourly message limit reached. Please try again later.")
        score = self.agent.llm.injection_score(value)
        result = WritePath(store, clock=self.clock(customer), allow_session=store is self.session_store).write(
            customer, uuid4().hex, value, [candidate], guard_score=score, allowed_orders={"QH1042"})
        if result.reasons:
            raise ValueError(", ".join(result.reasons))

    def revoke(self, customer, memory_id):
        self._pending.pop(customer, None)
        store, _ = self._record(customer, memory_id)
        return Forgetting(store, clock=self.clock(customer)).revoke(customer, memory_id)

    def forget_all(self, customer):
        self._pending.pop(customer, None)
        return sum(Forgetting(store, clock=self.clock(customer)).forget_all(customer) for store in (self.store, self.session_store))

    def history(self, customer, memory_id):
        store, record = self._record(customer, memory_id)
        return [row for row in self.snapshot(customer) if row["key"] == record.key and row["scope"] == record.scope]

    def export(self, customer):
        blocked, consented = self.store.privacy(customer)
        return {"memories": self.snapshot(customer), "blocked_categories": sorted(blocked), "consented_categories": sorted(consented),
                "audit": self.store.audit(customer) + self.session_store.audit(customer)}

    def reset(self, customer):
        self._pending.pop(customer, None)
        for store in (self.store, self.session_store):
            store.clear_customer(customer)
        with self._lock:
            self._clocks.pop(customer, None)
        self.initialize(customer)
        return self.snapshot(customer)

    def write_session(self, customer, message_id, candidate):
        blocked, consented = self.store.privacy(customer)
        self.session_store.set_privacy(customer, blocked=blocked, consented=consented)
        return WritePath(self.session_store, clock=self.clock(customer), allow_session=True).write(
            customer, message_id, candidate.quote, [candidate], guard_score=self.agent.llm.injection_score(candidate.quote))

    def respond(self, customer, message, history, *, incognito=False):
        self.initialize(customer)
        pending = self._pending.pop(customer, [])
        if not incognito and pending and message.casefold().strip(" .!?") in memory_config()["confirmation_replies"]:
            if not self.agent.limiter.allow(customer):
                from app.agent.orchestrator import TurnResult
                return TurnResult(reply="You've reached the demo's hourly message limit. Please try again later.", notes=["rate limited"])
            confirmed = []
            for memory_id in pending:
                try:
                    self.confirm(customer, memory_id)
                    confirmed.append(memory_id)
                except (KeyError, ValueError):
                    pass
            from app.agent.orchestrator import TurnResult
            return TurnResult(reply="Thanks, I confirmed those memories and refreshed their confidence." if confirmed else "Those memories could not be confirmed. Please review them in the inspector.", written_ids=confirmed)
        blocked, consented = self.store.privacy(customer)
        self.session_store.set_privacy(customer, blocked=blocked, consented=consented)
        result = self.agent.respond(customer, message, history, incognito=incognito, allowed_orders={"QH1042"},
                                    clock=self.clock(customer), session_store=self.session_store)
        if result.hedged_ids:
            self._pending[customer] = list(result.hedged_ids)
        return result
