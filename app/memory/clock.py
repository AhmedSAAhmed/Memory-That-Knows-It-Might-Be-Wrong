"""Injectable UTC clocks; a demo clock belongs to its caller, never a global."""
from datetime import datetime, timedelta, timezone
from typing import Protocol
from threading import RLock


def utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("A timezone-aware timestamp is required")
    return value.astimezone(timezone.utc)


class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)


class ManualClock:
    def __init__(self, current: datetime):
        self.current = utc(current)

    def now(self) -> datetime:
        return self.current

    def advance(self, *, days: float = 0, seconds: float = 0) -> None:
        self.current += timedelta(days=days, seconds=seconds)


class OffsetClock(SystemClock):
    def __init__(self):
        self.offset_days = 0
        self._last = None
        self._lock = RLock()

    def now(self) -> datetime:
        with self._lock:
            value = super().now() + timedelta(days=self.offset_days)
            if self._last is not None and value <= self._last:
                value = self._last + datetime.resolution
            self._last = value
            return value
