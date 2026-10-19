"""Streak transitions and display (docs/spec/07 §7.5, T-GAM-3)."""

from datetime import date, timedelta

import pytest

from app.gamification.streaks import Streak, record_streak_day, view_streak

D0 = date(2026, 11, 2)


def days(n: int) -> date:
    return D0 + timedelta(days=n)


def test_first_day_starts_at_one() -> None:
    s = record_streak_day(Streak(), D0)
    assert (s.current, s.longest, s.last_date, s.freezes_available) == (1, 1, D0, 1)


def test_same_day_and_earlier_day_change_nothing() -> None:
    s = record_streak_day(Streak(), D0)
    assert record_streak_day(s, D0) == s
    assert record_streak_day(s, days(-1)) == s  # timezone moved backwards


def test_consecutive_days_increment() -> None:
    s = Streak()
    for i in range(3):
        s = record_streak_day(s, days(i))
    assert s.current == 3


def test_single_missed_day_uses_a_freeze() -> None:
    s = record_streak_day(Streak(), D0)
    s = record_streak_day(s, days(2))
    assert (s.current, s.freezes_available, s.freezes_used_total) == (2, 0, 1)


def test_gap_larger_than_freezes_resets() -> None:
    s = record_streak_day(Streak(current=5, longest=5, last_date=D0, freezes_available=1), days(4))
    assert (s.current, s.longest, s.freezes_available) == (1, 5, 1)


def test_freeze_earned_every_seven_days_capped_at_two() -> None:
    s = Streak(freezes_available=1)
    freezes = []
    for i in range(21):
        s = record_streak_day(s, days(i))
        freezes.append(s.freezes_available)
    assert freezes[5] == 1  # day 6
    assert freezes[6] == 2  # day 7 earns one
    assert freezes[13] == 2  # day 14 would earn one but the cap is 2
    assert s.current == 21


def test_two_freezes_cover_two_missed_days() -> None:
    s = Streak(current=7, longest=7, last_date=D0, freezes_available=2)
    s = record_streak_day(s, days(3))
    assert (s.current, s.freezes_available) == (8, 0)


@pytest.mark.parametrize(
    ("offset", "freezes", "expected"),
    [
        (0, 1, (4, True, False)),  # done today
        (1, 0, (4, False, True)),  # yesterday was the last day, no freeze: act today
        (1, 1, (4, False, False)),  # a freeze would cover tomorrow's miss
        (2, 1, (4, False, True)),  # freeze covers yesterday; today is the last chance
        (3, 1, (0, False, False)),  # broken
    ],
)
def test_view(offset: int, freezes: int, expected: tuple[int, bool, bool]) -> None:
    s = Streak(current=4, longest=9, last_date=D0, freezes_available=freezes)
    v = view_streak(s, days(offset))
    assert (v.current, v.done_today, v.at_risk) == expected
    assert v.longest == 9


def test_view_without_history() -> None:
    v = view_streak(Streak(), D0)
    assert (v.current, v.done_today, v.at_risk, v.freezes_available) == (0, False, False, 1)
