"""Daily streak with automatic freezes (docs/spec/07 §7.5). Pure functions."""

from dataclasses import dataclass, replace
from datetime import date

FREEZES_INITIAL = 1
FREEZES_MAX = 2
FREEZE_EARNED_EVERY = 7


@dataclass(frozen=True)
class Streak:
    current: int = 0
    longest: int = 0
    last_date: date | None = None
    freezes_available: int = FREEZES_INITIAL
    freezes_used_total: int = 0


@dataclass(frozen=True)
class StreakView:
    current: int
    longest: int
    freezes_available: int
    done_today: bool
    at_risk: bool  # missing today would end the streak


def record_streak_day(streak: Streak, day: date) -> Streak:
    """Apply a qualifying activity (lesson completed / review session completed) on ``day``."""
    last = streak.last_date
    if last is not None and day <= last:  # same day, or an earlier day after a timezone change
        return streak
    freezes, used = streak.freezes_available, streak.freezes_used_total
    if last is None:
        current = 1
    elif (day - last).days == 1:
        current = streak.current + 1
    else:
        missed = (day - last).days - 1
        if missed <= freezes:
            freezes -= missed
            used += missed
            current = streak.current + 1
        else:
            current = 1
    if current > streak.current and current % FREEZE_EARNED_EVERY == 0:
        freezes = min(FREEZES_MAX, freezes + 1)
    return replace(
        streak,
        current=current,
        longest=max(streak.longest, current),
        last_date=day,
        freezes_available=freezes,
        freezes_used_total=used,
    )


def view_streak(streak: Streak, today: date) -> StreakView:
    """What to show today, without a background job: a broken streak simply reads as 0."""
    last = streak.last_date
    if last is None:
        return StreakView(0, streak.longest, streak.freezes_available, False, False)
    if today <= last:
        return StreakView(streak.current, streak.longest, streak.freezes_available, True, False)
    missed = (today - last).days - 1
    if missed <= streak.freezes_available:
        return StreakView(
            streak.current,
            streak.longest,
            streak.freezes_available,
            done_today=False,
            at_risk=missed + 1 > streak.freezes_available,
        )
    return StreakView(0, streak.longest, streak.freezes_available, False, False)
