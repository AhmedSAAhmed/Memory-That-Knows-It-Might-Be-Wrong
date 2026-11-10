"""Turn orchestration: guard -> (write path) -> (retrieval) -> answer.

Day 0: guard + answer with an empty evidence pack. The write and retrieval paths
plug in here on Day 1-2 (see stages/02_architecture).
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from app.config import get_settings, prompt
from app.llm.client import LLMClient, LLMUnavailable
from app.agent.limits import RateLimiter

log = logging.getLogger(__name__)

INJECTION_THRESHOLD = 0.9


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


class Agent:
    def __init__(self, llm: LLMClient | None = None, limiter: RateLimiter | None = None) -> None:
        s = get_settings()
        self.llm = llm or LLMClient()
        self.limiter = limiter or RateLimiter(s.max_messages_per_session_per_hour)

    def respond(self, session_id: str, message: str, history: list[dict]) -> TurnResult:
        message = (message or "").strip()[:2000]
        if not message:
            return TurnResult(reply="")
        if not self.limiter.allow(session_id):
            return TurnResult(reply="You've reached the demo's hourly message limit. Please try again later.",
                              notes=["rate limited"])

        score = self.llm.injection_score(message)
        notes: list[str] = []
        if score is not None and score >= INJECTION_THRESHOLD:
            notes.append(f"prompt-guard flagged message ({score:.2f}): nothing will be written to memory")

        evidence: list[dict] = []  # Day 1-2: retrieval.build_evidence(customer_id, message)
        system = prompt("answerer") + "\n\nEVIDENCE:\n" + (json.dumps(evidence, ensure_ascii=False) or "[]")
        msgs = [{"role": "system", "content": system}]
        msgs += [{"role": m["role"], "content": str(m["content"])} for m in history[-10:]
                 if m.get("role") in ("user", "assistant")]
        msgs.append({"role": "user", "content": message})

        try:
            res = self.llm.chat(msgs, json_mode=True)
        except LLMUnavailable as exc:
            log.error("answer failed: %s", exc)
            return TurnResult(reply="Sorry, I can't reach my language model right now. Please try again in a minute.",
                              injection_score=score, notes=notes + ["llm unavailable"])

        data = _parse_json(res.text)
        return TurnResult(
            reply=str(data.get("reply") or res.text),
            evidence=evidence,
            used_ids=[str(x) for x in data.get("used_ids") or []],
            hedged_ids=[str(x) for x in data.get("hedged_ids") or []],
            injection_score=score,
            provider=res.provider,
            model=res.model,
            notes=notes,
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
