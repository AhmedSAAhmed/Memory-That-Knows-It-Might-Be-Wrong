"""Deterministic write resolution; models cannot set identity, consent or time."""
from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4

from app.config import memory_config
from app.memory.clock import Clock, SystemClock, utc
from app.memory.models import Candidate, Memory
from app.memory.privacy import candidate_reason, message_reason, screening_reason
from app.memory.store import MemoryStore

CUSTOMER_SOURCES = {"user_stated", "user_confirmed"}


@dataclass
class WriteResult:
    stored_ids: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)


class WritePath:
    def __init__(self, store: MemoryStore, *, clock: Clock | None = None):
        self.store = store
        self.clock = clock or SystemClock()

    def write(self, customer_id: str, message_id: str, message: str, candidates: list[Candidate], *,
              guard_score: float | None = None, incognito: bool = False,
              allowed_orders: set[str] | None = None, occurred_at: datetime | None = None) -> WriteResult:
        if not customer_id or not message_id:
            raise ValueError("Server identity and source message ID are required")
        now = utc(self.clock.now())
        event_at = utc(occurred_at) if occurred_at else now
        if event_at > now:
            raise ValueError("Source event cannot be in the future")
        config = memory_config()
        if len(message) > config["limits"]["message_chars"] or len(candidates) > config["limits"]["max_candidates"]:
            raise ValueError("Write input exceeds configured limit")
        if any(not isinstance(candidate, Candidate) for candidate in candidates):
            raise ValueError("Validated candidates required")
        result = WriteResult()
        reason = "incognito" if incognito else message_reason(message) or screening_reason(guard_score)
        identities = [(candidate.scope, candidate.key) for candidate in candidates]
        if len(set(identities)) != len(identities):
            reason = reason or "ambiguous_candidates"
        with self.store.transaction() as db:
            if reason:
                self.store._audit(db, customer_id, "not_stored", now, reason=reason)
                return WriteResult(reasons=[reason])
            blocked, consented = self.store.privacy(customer_id)
            for candidate in candidates:
                reason = candidate_reason(candidate, message, blocked=blocked, consented=consented, allowed_orders=allowed_orders or set())
                if reason:
                    self.store._audit(db, customer_id, "not_stored", now, reason=reason)
                    result.reasons.append(reason)
                    continue
                replay = db.execute("SELECT memory_id FROM source_events WHERE customer_id=? AND scope=? AND key=? AND message_id=?",
                                    (customer_id, candidate.scope, candidate.key, message_id)).fetchone()
                if replay:
                    result.reasons.append("replayed_event")
                    continue
                current = self.store.list_memories(customer_id, scope=candidate.scope)
                current = [r for r in current if r.key == candidate.key]
                # A key's category is stable; a model cannot reset sensitivity or half-life.
                if current and any(r.category != candidate.category for r in current):
                    result.reasons.append("category_mismatch")
                    self.store._audit(db, customer_id, "not_stored", now, reason="category_mismatch")
                    continue
                memory_id = self._resolve(db, customer_id, message_id, candidate, current, now, event_at)
                db.execute("INSERT INTO source_events VALUES (?,?,?,?,?,?)", (customer_id, candidate.scope, candidate.key, message_id, memory_id, event_at.isoformat()))
                result.stored_ids.append(memory_id)
        return result

    def _status(self, db, record: Memory, status: str, now: datetime):
        db.execute("UPDATE memories SET status=? WHERE customer_id=? AND id=?", (status, record.customer_id, record.id))
        updated = self.store.get(record.customer_id, record.id)
        self.store._index(db, updated)
        self.store._audit(db, record.customer_id, status, now, memory_id=record.id)

    def _resolve(self, db, customer_id, message_id, candidate, current, now, event_at):
        config = memory_config()
        incoming_customer = candidate.source in CUSTOMER_SOURCES
        same = next((r for r in current if r.value.casefold() == candidate.value.casefold()), None)
        conflicting = [r for r in current if r is not same]
        # A fresh explicit statement also resolves a previously contested same value.
        resolvable = incoming_customer and conflicting and all(
            r.source not in CUSTOMER_SOURCES or event_at > r.event_at for r in conflicting)
        if same and not resolvable:
            stronger = (incoming_customer and same.source in CUSTOMER_SOURCES) or config["source_base_confidence"][candidate.source] >= same.base_confidence
            refresh = stronger and (event_at > same.last_confirmed_at or (
                event_at == same.last_confirmed_at and config["source_base_confidence"][candidate.source] > same.base_confidence))
            db.execute("UPDATE memories SET corroborations=corroborations+1 WHERE customer_id=? AND id=?", (customer_id, same.id))
            if refresh:
                db.execute("""UPDATE memories SET source=?,source_message_id=?,quote=?,text=?,base_confidence=?,
                              last_confirmed_at=?,event_at=?,status=CASE WHEN status='stale' THEN 'active' ELSE status END
                              WHERE customer_id=? AND id=?""",
                           (candidate.source, message_id, candidate.quote, candidate.text,
                            config["source_base_confidence"][candidate.source], event_at.isoformat(), event_at.isoformat(), customer_id, same.id))
            self.store._index(db, self.store.get(customer_id, same.id))
            self.store._audit(db, customer_id, "corroborated", now, memory_id=same.id)
            return same.id

        # Decide against the whole group before changing any older records.
        # An out-of-order candidate must not partially overwrite a contested group.
        customer_facts = [r for r in current if r.source in CUSTOMER_SOURCES]
        loses = customer_facts and (not incoming_customer or any(event_at < r.event_at for r in customer_facts))
        status = "superseded" if loses else "active"
        supersedes = None
        for old in ([] if loses else current):
            old_customer = old.source in CUSTOMER_SOURCES
            if incoming_customer and (not old_customer or event_at > old.event_at):
                self._status(db, old, "superseded", now)
                supersedes = old.id
            elif old_customer and (not incoming_customer or event_at < old.event_at):
                status = "superseded"
            else:
                self._status(db, old, "contested", now)
                status = "contested"
        # A single losing candidate must never supersede any winning current facts.
        if status == "superseded":
            supersedes = None
        record = Memory(uuid4().hex, customer_id, candidate.scope, candidate.category, candidate.key,
                        candidate.value, candidate.text, candidate.source, message_id, candidate.quote,
                        config["source_base_confidence"][candidate.source], now, event_at, event_at,
                        status, supersedes, 0)
        data = record.__dict__.copy()
        for name in ("created_at", "last_confirmed_at", "event_at"):
            data[name] = data[name].isoformat()
        db.execute("INSERT INTO memories (" + ",".join(data) + ") VALUES (" + ",".join("?" for _ in data) + ")", tuple(data.values()))
        self.store._index(db, record)
        self.store._audit(db, customer_id, "written", now, memory_id=record.id)
        return record.id
