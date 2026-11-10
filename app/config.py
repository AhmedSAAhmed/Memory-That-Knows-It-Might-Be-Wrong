"""Settings, factory paths and the memory config. Numbers live in _shared/memory-config.json."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
SHARED = ROOT / "_shared"
PROMPTS = SHARED / "prompts"

load_dotenv(ROOT / ".env")

VERSION = "0.1.0"


_QUOTES = "\"'“”‘’"


def _env(name: str, default: str = "") -> str:
    """Read an env var, tolerating stray straight or smart quotes around the value."""
    return os.getenv(name, default).strip().strip(_QUOTES).strip()


@dataclass(frozen=True)
class Settings:
    groq_api_key: str
    openrouter_api_key: str
    gemini_api_key: str
    groq_chat_model: str
    groq_fast_model: str
    groq_guard_model: str
    openrouter_chat_model: str
    gemini_chat_model: str
    gemini_embed_model: str
    database_path: Path
    max_messages_per_session_per_hour: int
    max_output_tokens: int


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    db = Path(_env("DATABASE_PATH", "data/memory.db"))
    if not db.is_absolute():
        db = ROOT / db
    return Settings(
        groq_api_key=_env("GROQ_API_KEY"),
        openrouter_api_key=_env("OPENROUTER_API_KEY"),
        gemini_api_key=_env("GEMINI_API_KEY"),
        groq_chat_model=_env("GROQ_CHAT_MODEL", "openai/gpt-oss-120b"),
        groq_fast_model=_env("GROQ_FAST_MODEL", "openai/gpt-oss-20b"),
        groq_guard_model=_env("GROQ_GUARD_MODEL", "meta-llama/llama-prompt-guard-2-86m"),
        openrouter_chat_model=_env("OPENROUTER_CHAT_MODEL", "openai/gpt-oss-120b"),
        gemini_chat_model=_env("GEMINI_CHAT_MODEL", "gemini-2.5-flash"),
        gemini_embed_model=_env("GEMINI_EMBED_MODEL", "gemini-embedding-001"),
        database_path=db,
        max_messages_per_session_per_hour=int(_env("MAX_MESSAGES_PER_SESSION_PER_HOUR", "60")),
        max_output_tokens=int(_env("MAX_OUTPUT_TOKENS", "900")),
    )


@lru_cache(maxsize=1)
def memory_config() -> dict:
    return json.loads((SHARED / "memory-config.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=None)
def prompt(name: str) -> str:
    """Load a prompt from _shared/prompts/<name>.md, dropping its title line."""
    text = (PROMPTS / f"{name}.md").read_text(encoding="utf-8")
    lines = text.splitlines()
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
    return "\n".join(lines).strip()
