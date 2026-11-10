"""SQLite persistence with transactional writes, FTS5 and identity-bound reads."""
from contextlib import contextmanager
from datetime import datetime
import json
from pathlib import Path
import re
import sqlite3
import math
from threading import RLock
from uuid import uuid4

from app.config import memory_config
from app.memory.models import Memory


class MemoryStore:
    def __init__(self, path: str | Path = ":memory:"):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._db = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA foreign_keys=ON")
        self._db.execute("PRAGMA secure_delete=ON")
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.executescript("""
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY, customer_id TEXT NOT NULL, scope TEXT NOT NULL,
                category TEXT NOT NULL, key TEXT NOT NULL, value TEXT NOT NULL,
                text TEXT NOT NULL, source TEXT NOT NULL, source_message_id TEXT NOT NULL,
                quote TEXT NOT NULL, base_confidence REAL NOT NULL,
                created_at TEXT NOT NULL, last_confirmed_at TEXT NOT NULL, event_at TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('active','stale','contested','superseded','revoked')),
                supersedes TEXT REFERENCES memories(id), corroborations INTEGER NOT NULL DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS memory_scope_key ON memories(customer_id,scope,key,status);
            CREATE TABLE IF NOT EXISTS source_events (
                customer_id TEXT NOT NULL, scope TEXT NOT NULL, key TEXT NOT NULL,
                message_id TEXT NOT NULL, memory_id TEXT NOT NULL REFERENCES memories(id),
                occurred_at TEXT NOT NULL,
                PRIMARY KEY(customer_id,scope,key,message_id)
            );
            CREATE TABLE IF NOT EXISTS privacy (
                customer_id TEXT PRIMARY KEY, blocked TEXT NOT NULL, consented TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS audit (
                id TEXT PRIMARY KEY, customer_id TEXT NOT NULL, action TEXT NOT NULL,
                memory_id TEXT, reason TEXT, at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS tombstones (
                customer_id TEXT NOT NULL, scope TEXT NOT NULL, key TEXT NOT NULL,
                category TEXT NOT NULL, revoked_at TEXT NOT NULL,
                PRIMARY KEY(customer_id,scope,key)
            );
            CREATE TABLE IF NOT EXISTS embeddings (
                memory_id TEXT PRIMARY KEY REFERENCES memories(id), customer_id TEXT NOT NULL,
                vector TEXT NOT NULL
            );
            CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
                memory_id UNINDEXED, customer_id UNINDEXED, scope UNINDEXED, key, value, text
            );
        """)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self):
        with self._lock:
            self._db.close()

    @contextmanager
    def transaction(self):
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                yield self._db
                self._db.execute("COMMIT")
            except BaseException:
                self._db.execute("ROLLBACK")
                raise

    @staticmethod
    def _memory(row) -> Memory:
        data = dict(row)
        for field in ("created_at", "last_confirmed_at", "event_at"):
            data[field] = datetime.fromisoformat(data[field])
        return Memory(**data)

    def get(self, customer_id: str, memory_id: str) -> Memory | None:
        with self._lock:
            row = self._db.execute("SELECT * FROM memories WHERE customer_id=? AND id=?", (customer_id, memory_id)).fetchone()
            return self._memory(row) if row else None

    def list_memories(self, customer_id: str, *, scope: str = "customer", include_history: bool = False) -> list[Memory]:
        sql = "SELECT * FROM memories WHERE customer_id=? AND scope=?"
        if not include_history:
            sql += " AND status IN ('active','stale','contested')"
        with self._lock:
            return [self._memory(r) for r in self._db.execute(sql + " ORDER BY rowid", (customer_id, scope))]

    def search(self, customer_id: str, query: str, *, scope: str = "customer", match_any: bool = False) -> list[Memory]:
        tokens = re.findall(r"\w+", query, flags=re.UNICODE)
        if not tokens:
            return []
        expression = (" OR " if match_any else " AND ").join('"' + token + '"' for token in tokens)
        with self._lock:
            rows = self._db.execute("""
                SELECT m.* FROM memories m JOIN memories_fts f ON f.memory_id=m.id
                WHERE m.customer_id=? AND m.scope=? AND f.customer_id=? AND f.scope=?
                AND m.status IN ('active','stale','contested') AND memories_fts MATCH ?
                ORDER BY rank
            """, (customer_id, scope, customer_id, scope, expression)).fetchall()
            return [self._memory(r) for r in rows]

    def set_privacy(self, customer_id: str, *, blocked: set[str], consented: set[str]) -> None:
        if (blocked | consented) - memory_config()["categories"].keys():
            raise ValueError("Unknown privacy category")
        with self.transaction() as db:
            db.execute("INSERT INTO privacy VALUES (?,?,?) ON CONFLICT(customer_id) DO UPDATE SET blocked=excluded.blocked,consented=excluded.consented",
                       (customer_id, json.dumps(sorted(blocked)), json.dumps(sorted(consented))))

    def privacy(self, customer_id: str) -> tuple[set[str], set[str]]:
        with self._lock:
            row = self._db.execute("SELECT blocked,consented FROM privacy WHERE customer_id=?", (customer_id,)).fetchone()
            return (set(json.loads(row[0])), set(json.loads(row[1]))) if row else (set(), set())

    def _audit(self, db, customer_id: str, action: str, at: datetime, *, memory_id=None, reason=None):
        db.execute("INSERT INTO audit VALUES (?,?,?,?,?,?)", (uuid4().hex, customer_id, action, memory_id, reason, at.isoformat()))

    def audit(self, customer_id: str) -> list[dict]:
        with self._lock:
            return [dict(r) for r in self._db.execute("SELECT * FROM audit WHERE customer_id=? ORDER BY rowid", (customer_id,))]

    def _index(self, db, record: Memory):
        db.execute("DELETE FROM memories_fts WHERE memory_id=? AND customer_id=?", (record.id, record.customer_id))
        db.execute("DELETE FROM embeddings WHERE memory_id=? AND customer_id=?", (record.id, record.customer_id))
        if record.status in {"active", "stale", "contested"}:
            db.execute("INSERT INTO memories_fts VALUES (?,?,?,?,?,?)", (record.id, record.customer_id, record.scope, record.key, record.value, record.text))

    def put_embedding(self, customer_id: str, memory_id: str, vector: list[float], *, expected_text: str | None = None) -> bool:
        if not vector or len(vector) > memory_config()["retrieval"]["embedding_dimensions"] or any(
            isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in vector
        ) or not any(vector):
            return False
        with self.transaction() as db:
            record = self.get(customer_id, memory_id)
            if not record or record.status not in {"active", "stale", "contested"}:
                return False
            if expected_text is not None and expected_text != record.text:
                return False
            db.execute("INSERT INTO embeddings VALUES (?,?,?) ON CONFLICT(memory_id) DO UPDATE SET vector=excluded.vector",
                       (memory_id, customer_id, json.dumps(vector)))
            return True

    def embeddings(self, customer_id: str, *, scope: str = "customer") -> dict[str, list[float]]:
        with self._lock:
            rows = self._db.execute("""SELECT e.memory_id,e.vector FROM embeddings e JOIN memories m ON m.id=e.memory_id
                WHERE e.customer_id=? AND m.customer_id=? AND m.scope=? AND m.status IN ('active','stale','contested')""",
                                    (customer_id, customer_id, scope))
            return {r[0]: json.loads(r[1]) for r in rows}

    def tombstone(self, customer_id: str, scope: str, key: str) -> dict | None:
        with self._lock:
            row = self._db.execute("SELECT * FROM tombstones WHERE customer_id=? AND scope=? AND key=?", (customer_id, scope, key)).fetchone()
            return dict(row) if row else None

    def unrestored_tombstones(self, customer_id: str, *, scope: str = "customer") -> list[dict]:
        """Only erased keys without a current replacement; payloads stay erased."""
        with self._lock:
            rows = self._db.execute("""SELECT t.* FROM tombstones t WHERE t.customer_id=? AND t.scope=?
                AND NOT EXISTS (SELECT 1 FROM memories m WHERE m.customer_id=t.customer_id
                    AND m.scope=t.scope AND m.key=t.key AND m.status IN ('active','stale','contested'))""",
                                    (customer_id, scope)).fetchall()
            return [dict(row) for row in rows]

    def all_memories(self, customer_id: str, *, include_history: bool = True) -> list[Memory]:
        with self._lock:
            sql = "SELECT * FROM memories WHERE customer_id=?"
            if not include_history:
                sql += " AND status IN ('active','stale','contested')"
            return [self._memory(row) for row in self._db.execute(sql + " ORDER BY rowid", (customer_id,))]

    def clear_customer(self, customer_id: str) -> None:
        """Explicit demo reset / transient-session expiry, always identity-bound."""
        with self.transaction() as db:
            for table in ("memories_fts", "embeddings", "source_events", "memories", "tombstones", "privacy", "audit"):
                db.execute(f"DELETE FROM {table} WHERE customer_id=?", (customer_id,))
