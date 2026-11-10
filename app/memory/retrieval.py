"""Scoped FTS/embedding retrieval; confidence is applied exactly once."""
import math
import re

from app.config import memory_config
from app.memory.clock import SystemClock
from app.memory.confidence import assess
from app.memory.evidence import build_evidence


def cosine(left, right) -> float:
    if not left or len(left) != len(right):
        return 0.0
    if any(not isinstance(x, (int, float)) or not math.isfinite(x) for x in [*left, *right]):
        return 0.0
    norm = math.sqrt(sum(x*x for x in left) * sum(x*x for x in right))
    return max(0.0, sum(a*b for a,b in zip(left, right)) / norm) if norm else 0.0


class Retriever:
    def __init__(self, store, *, clock=None, embedder=None):
        self.store = store
        self.clock = clock or SystemClock()
        self.embedder = embedder

    def retrieve(self, customer_id: str, query: str, *, scopes: tuple[str, ...] = ("customer",)) -> list[dict]:
        config = memory_config()
        terms = set(re.findall(r"\w+", query.casefold()))
        listing = bool(re.search(config["list_query_pattern"], query))
        query_vector = None
        if self.embedder and not listing:
            try:
                query_vector = self.embedder(query)
            except Exception:
                pass  # FTS remains usable without a vector provider.
        ranked = []
        now = self.clock.now()
        for scope in dict.fromkeys(scopes):
            records = self.store.list_memories(customer_id, scope=scope)
            hits = {r.id for r in self.store.search(customer_id, query, scope=scope, match_any=True)} if terms else set()
            vectors = self.store.embeddings(customer_id, scope=scope)
            for record in records:
                aliases = set(config["query_terms"].get(record.category, []))
                lexical = float(listing or record.id in hits or bool(terms & aliases))
                semantic = cosine(query_vector, vectors.get(record.id, [])) if query_vector else 0.0
                relevance = config["retrieval"]["lexical_weight"] * lexical + config["retrieval"]["embedding_weight"] * semantic
                if relevance > 0:
                    ranked.append((relevance * assess(record, now).effective, record))
        ranked.sort(key=lambda entry: entry[0], reverse=True)
        evidence = [build_evidence(record, now) for _,record in ranked[:config["retrieval"]["limit"]]]
        if evidence:
            with self.store.transaction() as db:
                for item in evidence:
                    self.store._audit(db, customer_id, "read_for_answer", now, memory_id=item["id"])
        return evidence
