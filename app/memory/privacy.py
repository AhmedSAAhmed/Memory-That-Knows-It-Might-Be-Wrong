"""Conservative, deterministic checks before anything can become memory."""
import math
import re

from app.config import memory_config
from app.memory.models import Candidate


def message_reason(message: str) -> str | None:
    config = memory_config()
    if any(re.search(pattern, message) for pattern in config["secret_patterns"]):
        return "secret_detected"
    if any(re.search(pattern, message) for pattern in config["instruction_patterns"]):
        return "instruction_like"
    return None


def screening_reason(score: float | None) -> str | None:
    if isinstance(score, bool) or not isinstance(score, (float, int)) or not math.isfinite(score) or not 0 <= score <= 1:
        return "screening_unavailable"
    if score >= memory_config()["guard_threshold"]:
        return "instruction_like"
    return None


def candidate_reason(candidate: Candidate, message: str, *, blocked: set[str], consented: set[str],
                     allowed_orders: set[str], allow_session: bool = False) -> str | None:
    if candidate.scope == "session" and not allow_session:
        return "session_scope_not_persisted"
    if candidate.scope.startswith("order:") and candidate.scope[6:] not in allowed_orders:
        return "unauthorized_scope"
    if candidate.quote not in message:
        return "invalid_quote"
    config = memory_config()
    content = " ".join((message, candidate.value, candidate.text, candidate.key, candidate.quote))
    reason = message_reason(content)
    if reason:
        return reason
    sensitivity = config["categories"][candidate.category]["sensitivity"]
    if sensitivity == "secret":
        return "secret_detected"
    detected = {category for category, pattern in config["sensitive_patterns"].items() if re.search(pattern, content)}
    categories = detected | {candidate.category}
    if categories & blocked:
        return "blocked_category"
    required = detected | ({candidate.category} if sensitivity == "sensitive" else set())
    if required - consented:
        return "consent_required"
    return None
