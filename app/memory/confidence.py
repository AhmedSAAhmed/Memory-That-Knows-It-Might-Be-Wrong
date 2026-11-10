"""Source confidence, decaying corroboration and behavior bands."""
from dataclasses import dataclass
from datetime import datetime

from app.config import memory_config
from app.memory.clock import utc
from app.memory.models import Memory


@dataclass(frozen=True)
class Assessment:
    effective: float
    band: str
    stale: bool
    age_days: float


def assess(record: Memory, now: datetime) -> Assessment:
    config = memory_config()
    age = max(0.0, (utc(now) - record.last_confirmed_at).total_seconds() / 86400)
    half_life = config["categories"][record.category]["half_life_days"]
    if record.status in {"revoked", "superseded"} or half_life <= 0:
        return Assessment(0.0, "ask", False, age)
    base = min(config["corroboration_cap"], record.base_confidence + record.corroborations * config["corroboration_boost"])
    effective = base * 0.5 ** (age / half_life)
    if record.status == "contested":
        effective -= config["contested_penalty"]
    effective = max(0.0, effective)
    stale = record.status == "stale" or age >= half_life * config["stale_after_fraction_of_half_life"]
    band = "ask"
    if record.status != "contested" and effective >= config["thresholds"]["hedge"]:
        band = "assert" if effective >= config["thresholds"]["assert"] and not stale else "hedge"
    return Assessment(effective, band, stale, age)
