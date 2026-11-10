"""Only safe evidence crosses the memory-to-answer boundary."""
from datetime import datetime

from app.memory.confidence import assess
from app.memory.models import Memory


def build_evidence(record: Memory, now: datetime) -> dict:
    assessment = assess(record, now)
    item = {"id": record.id, "key": record.key, "category": record.category, "scope": record.scope,
            "confidence": assessment.effective, "band": assessment.band, "age": f"{assessment.age_days:.0f} days"}
    if assessment.band == "ask":
        item["text"] = f"Please confirm your {record.key.replace('_', ' ')}."
    else:
        item.update(value=record.value, text=record.text, quote=record.quote, source=record.source,
                    source_message_id=record.source_message_id)
    return item
