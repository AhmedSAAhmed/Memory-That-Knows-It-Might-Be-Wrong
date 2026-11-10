"""Typed facts validated independently of the extraction model."""
from dataclasses import dataclass
from datetime import datetime
import re

from app.config import memory_config


@dataclass(frozen=True)
class Candidate:
    category: str
    key: str
    value: str
    text: str
    source: str
    quote: str
    scope: str = "customer"

    def __post_init__(self):
        config = memory_config()
        for name in self.__dataclass_fields__:
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"Invalid candidate field: {name}")
            if len(value) > config["limits"]["field_chars"]:
                raise ValueError(f"Candidate field too long: {name}")
            object.__setattr__(self, name, value.strip())
        if self.category not in config["categories"]:
            raise ValueError("Unknown category")
        canonical_key = config.get("key_aliases", {}).get(self.category, {}).get(self.key, self.key)
        object.__setattr__(self, "key", canonical_key)
        if self.source not in config["source_base_confidence"]:
            raise ValueError("Unknown source")
        if len(self.key) > config["limits"]["key_chars"] or not re.fullmatch(r"[a-z][a-z0-9_]*", self.key):
            raise ValueError("Invalid fact key")
        if not re.fullmatch(r"customer|session|order:[A-Za-z0-9_-]+", self.scope):
            raise ValueError("Invalid scope")


@dataclass(frozen=True)
class Memory:
    id: str
    customer_id: str
    scope: str
    category: str
    key: str
    value: str
    text: str
    source: str
    source_message_id: str
    quote: str
    base_confidence: float
    created_at: datetime
    last_confirmed_at: datetime
    event_at: datetime
    status: str
    supersedes: str | None
    corroborations: int
