"""One OpenAI-compatible client over Groq -> OpenRouter -> Gemini, with fallback."""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Any, Sequence

from openai import OpenAI

from app.config import Settings, get_settings, memory_config

log = logging.getLogger(__name__)

GROQ_URL = "https://api.groq.com/openai/v1"
OPENROUTER_URL = "https://openrouter.ai/api/v1"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"


@dataclass(frozen=True)
class Provider:
    name: str
    base_url: str
    api_key: str
    chat_model: str
    fast_model: str


@dataclass(frozen=True)
class LLMResult:
    text: str
    provider: str
    model: str


class LLMUnavailable(RuntimeError):
    """Every configured provider failed."""


def providers_from_settings(s: Settings) -> list[Provider]:
    out: list[Provider] = []
    if s.groq_api_key:
        out.append(Provider("groq", GROQ_URL, s.groq_api_key, s.groq_chat_model, s.groq_fast_model))
    if s.openrouter_api_key:
        out.append(Provider("openrouter", OPENROUTER_URL, s.openrouter_api_key,
                            s.openrouter_chat_model, s.openrouter_chat_model))
    if s.gemini_api_key:
        out.append(Provider("gemini", GEMINI_URL, s.gemini_api_key, s.gemini_chat_model, s.gemini_chat_model))
    return out


class LLMClient:
    def __init__(self, providers: Sequence[Provider] | None = None, *, timeout: float = 30.0,
                 settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.providers = list(providers) if providers is not None else providers_from_settings(self.settings)
        self._clients: dict[str, Any] = {}
        self.timeout = timeout

    def _client(self, p: Provider) -> Any:
        if p.name not in self._clients:
            self._clients[p.name] = OpenAI(api_key=p.api_key, base_url=p.base_url,
                                           timeout=self.timeout, max_retries=1)
        return self._clients[p.name]

    def chat(self, messages: list[dict], *, fast: bool = False, json_mode: bool = False,
             max_tokens: int | None = None, temperature: float = 0.2) -> LLMResult:
        if not self.providers:
            raise LLMUnavailable("No LLM provider configured: set GROQ_API_KEY (or a fallback key).")
        errors: list[str] = []
        for p in self.providers:
            model = p.fast_model if fast else p.chat_model
            kwargs: dict[str, Any] = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens or self.settings.max_output_tokens,
            }
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}
            if "gpt-oss" in model:
                # reasoning models spend max_tokens on thinking first; keep it short
                kwargs["reasoning_effort"] = "low"
                kwargs["max_tokens"] = max(kwargs["max_tokens"], 600)
            try:
                resp = self._client(p).chat.completions.create(**kwargs)
                text = (resp.choices[0].message.content or "").strip()
                if not text:
                    raise ValueError("empty completion")
                return LLMResult(text=text, provider=p.name, model=model)
            except Exception as exc:  # fall through to next provider
                log.warning("LLM provider %s failed (%s)", p.name, type(exc).__name__)
                errors.append(f"{p.name}: {type(exc).__name__}")
        raise LLMUnavailable("All providers failed: " + "; ".join(errors))

    def injection_score(self, text: str) -> float | None:
        """Prompt-guard score in [0, 1] (high = likely injection). None if the guard is unreachable."""
        groq = next((p for p in self.providers if p.name == "groq"), None)
        if groq is None:
            return None
        try:
            resp = self._client(groq).chat.completions.create(
                model=self.settings.groq_guard_model,
                messages=[{"role": "user", "content": text[:memory_config()["limits"]["message_chars"]]}],
                max_tokens=8,
                temperature=0,
            )
            score = float((resp.choices[0].message.content or "").strip())
            return score if math.isfinite(score) and 0 <= score <= 1 else None
        except Exception as exc:
            log.warning("prompt guard failed (%s)", type(exc).__name__)
            return None

    def embed(self, text: str) -> list[float] | None:
        """Optional Gemini embeddings; every failure leaves FTS5 usable."""
        gemini = next((provider for provider in self.providers if provider.name == "gemini"), None)
        if gemini is None:
            return None
        try:
            result = self._client(gemini).embeddings.create(
                model=self.settings.gemini_embed_model, input=text,
                dimensions=memory_config()["retrieval"]["embedding_dimensions"],
            )
            return result.data[0].embedding
        except Exception as exc:
            log.warning("embedding unavailable (%s)", type(exc).__name__)
            return None
