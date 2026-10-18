"""Injectable time source. Domain code must use a Clock, never datetime.now()."""

from datetime import UTC, date, datetime, timedelta
from typing import Protocol
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class Clock(Protocol):
    def now(self) -> datetime:
        """Current time as a timezone-aware UTC datetime."""
        ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class FixedClock:
    """Deterministic clock for tests; advance it explicitly."""

    def __init__(self, at: datetime) -> None:
        if at.tzinfo is None:
            raise ValueError("FixedClock requires a timezone-aware datetime")
        self._now = at.astimezone(UTC)

    def now(self) -> datetime:
        return self._now

    def set(self, at: datetime) -> None:
        if at.tzinfo is None:
            raise ValueError("FixedClock requires a timezone-aware datetime")
        self._now = at.astimezone(UTC)

    def advance(self, delta: timedelta) -> None:
        self._now += delta


def resolve_timezone(name: str | None) -> ZoneInfo:
    """Return the IANA zone, falling back to UTC for missing or unknown names."""
    if not name:
        return ZoneInfo("UTC")
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


def to_local_date(moment: datetime, timezone: str | None) -> date:
    """Calendar date of ``moment`` in the user's timezone (the 'local date' of the spec)."""
    return moment.astimezone(resolve_timezone(timezone)).date()


def local_date(clock: Clock, timezone: str | None) -> date:
    return to_local_date(clock.now(), timezone)
