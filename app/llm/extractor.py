"""Treat model output as untrusted JSON, then validate every candidate."""
from dataclasses import dataclass, field
import json

from app.config import memory_config, prompt
from app.memory.models import Candidate
from app.memory.privacy import message_reason, screening_reason


class ExtractionError(ValueError):
    """Invalid model output; never include the raw response in errors or logs."""


@dataclass
class Extraction:
    candidates: list[Candidate] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)


class Extractor:
    def __init__(self, llm):
        self.llm = llm

    def extract(self, message: str, *, guard_score: float | None) -> Extraction:
        reason = message_reason(message) or screening_reason(guard_score)
        if reason:
            return Extraction(reasons=[reason])
        config = memory_config()
        if len(message) > config["limits"]["message_chars"]:
            raise ExtractionError("Message exceeds limit")
        system = prompt("extractor").replace("{categories}", ", ".join(config["categories"]))
        system = system.replace("{key_aliases}", json.dumps(config["key_aliases"]))
        result = self.llm.chat([{"role": "system", "content": system}, {"role": "user", "content": message}],
                               fast=True, json_mode=True, temperature=0)
        try:
            data = json.loads(result.text)
            required = {"candidates", "secret_detected", "instruction_like"}
            if not isinstance(data, dict) or set(data) != required:
                raise ValueError
            if any(type(data[name]) is not bool for name in ("secret_detected", "instruction_like")):
                raise ValueError
            if not isinstance(data["candidates"], list) or len(data["candidates"]) > config["limits"]["max_candidates"]:
                raise ValueError
            reasons = [name for name in ("secret_detected", "instruction_like") if data[name]]
            if reasons:
                return Extraction(reasons=reasons)
            candidates = []
            keys = set()
            fields = set(Candidate.__dataclass_fields__)
            for item in data["candidates"]:
                if not isinstance(item, dict) or set(item) != fields:
                    raise ValueError
                candidate = Candidate(**item)
                identity = (candidate.scope, candidate.key)
                if identity in keys or candidate.source not in {"user_stated", "inferred"}:
                    raise ValueError
                if candidate.quote not in message:
                    raise ValueError
                keys.add(identity)
                candidates.append(candidate)
            return Extraction(candidates=candidates)
        except (TypeError, ValueError):
            raise ExtractionError("Invalid extraction response") from None
