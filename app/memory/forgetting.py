"""Decay sweeps and erasure with content-free replay barriers."""
from app.memory.clock import SystemClock
from app.memory.confidence import assess


class Forgetting:
    def __init__(self, store, *, clock=None):
        self.store = store
        self.clock = clock or SystemClock()

    def sweep(self, customer_id: str | None = None) -> int:
        now = self.clock.now()
        count = 0
        with self.store.transaction() as db:
            sql = "SELECT * FROM memories WHERE status='active'"
            rows = db.execute(sql + (" AND customer_id=?" if customer_id else ""), (customer_id,) if customer_id else ()).fetchall()
            for row in rows:
                record = self.store._memory(row)
                if assess(record, now).stale:
                    db.execute("UPDATE memories SET status='stale' WHERE id=? AND customer_id=?", (record.id, record.customer_id))
                    self.store._audit(db, record.customer_id, "decay", now, memory_id=record.id)
                    count += 1
        return count

    def revoke(self, customer_id: str, memory_id: str) -> bool:
        now = self.clock.now()
        with self.store.transaction() as db:
            record = self.store.get(customer_id, memory_id)
            if record is None:
                return False
            rows = db.execute("SELECT id FROM memories WHERE customer_id=? AND scope=? AND key=?",
                              (customer_id, record.scope, record.key)).fetchall()
            for row in rows:
                db.execute("DELETE FROM memories_fts WHERE memory_id=? AND customer_id=?", (row[0], customer_id))
                db.execute("DELETE FROM embeddings WHERE memory_id=? AND customer_id=?", (row[0], customer_id))
            db.execute("""UPDATE memories SET value='',text='',quote='',base_confidence=0,corroborations=0,status='revoked'
                WHERE customer_id=? AND scope=? AND key=?""", (customer_id, record.scope, record.key))
            db.execute("INSERT INTO tombstones VALUES (?,?,?,?,?) ON CONFLICT(customer_id,scope,key) DO UPDATE SET revoked_at=excluded.revoked_at",
                       (customer_id, record.scope, record.key, record.category, now.isoformat()))
            self.store._audit(db, customer_id, "revoke", now, memory_id=memory_id)
            db.execute("INSERT INTO memories_fts(memories_fts) VALUES ('optimize')")
        # Minimize residual WAL copies after logical erasure; another reader can defer truncation.
        with self.store._lock:
            self.store._db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        return True

    def forget_all(self, customer_id: str) -> int:
        records = self.store.all_memories(customer_id, include_history=False)
        identities = {}
        for record in records:
            identities[(record.scope, record.key)] = record.id
        return sum(self.revoke(customer_id, memory_id) for memory_id in identities.values())
