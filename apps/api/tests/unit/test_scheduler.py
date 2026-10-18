"""sm2-curiosity-v1 against the worked examples in docs/spec/07 §7.3.5 (T-REC-1..3)."""

import uuid
from datetime import date
from decimal import Decimal

import pytest

from app.learning.grading import is_correct, selection_problem
from app.reviews.scheduler import ReviewSchedule, Sm2Scheduler, mastery_stage

S = Sm2Scheduler()


def test_worked_example_table() -> None:
    state = S.initial_state(date(2026, 11, 2))
    assert state == ReviewSchedule(Decimal("2.50"), 1, 0, 0, date(2026, 11, 3))

    steps = [
        # (reviewed_on, is_correct, guessed) -> (q, EF, interval, reps, lapses, due_on)
        ((date(2026, 11, 3), True, False), (4, "2.50", 6, 1, 0, date(2026, 11, 9))),
        ((date(2026, 11, 9), True, True), (3, "2.36", 15, 2, 0, date(2026, 11, 24))),
        ((date(2026, 11, 24), False, False), (1, "2.16", 1, 0, 1, date(2026, 11, 25))),
        ((date(2026, 11, 27), True, False), (4, "2.16", 6, 1, 1, date(2026, 12, 3))),
        ((date(2026, 12, 3), True, False), (4, "2.16", 13, 2, 1, date(2026, 12, 16))),
    ]
    for (reviewed_on, correct, guessed), (q, ef, interval, reps, lapses, due) in steps:
        grade = S.grade(is_correct=correct, guessed=guessed)
        assert grade == q
        state = S.next_state(state, grade, reviewed_on)
        assert state == ReviewSchedule(Decimal(ef), interval, reps, lapses, due)


def test_quality_mapping() -> None:
    assert S.grade(is_correct=False, guessed=False) == 1
    assert S.grade(is_correct=False, guessed=True) == 1
    assert S.grade(is_correct=True, guessed=True) == 3
    assert S.grade(is_correct=True, guessed=False) == 4


def test_ease_factor_floor() -> None:
    state = S.initial_state(date(2026, 1, 1))
    for _ in range(10):
        state = S.next_state(state, 1, date(2026, 1, 2))
    assert state.ease_factor == Decimal("1.30")
    assert state.lapses == 10


def test_interval_cap_and_growth_sequence() -> None:
    state = S.initial_state(date(2026, 1, 1))
    intervals = []
    for _ in range(6):
        state = S.next_state(state, 4, date(2026, 1, 1))
        intervals.append(state.interval_days)
    assert intervals == [6, 15, 38, 95, 180, 180]


def test_interval_always_grows_after_success() -> None:
    low = ReviewSchedule(Decimal("1.30"), 1, 1, 3, date(2026, 1, 1))
    assert S.next_state(low, 4, date(2026, 1, 1)).interval_days == 2


def test_rejects_unknown_quality() -> None:
    with pytest.raises(ValueError, match="unsupported quality"):
        S.next_state(S.initial_state(date(2026, 1, 1)), 5, date(2026, 1, 2))


@pytest.mark.parametrize(
    ("completed", "reps", "stage"),
    [(False, 0, 0), (True, 0, 1), (True, 1, 2), (True, 2, 3), (True, 3, 4), (True, 9, 4)],
)
def test_mastery_stage(completed: bool, reps: int, stage: int) -> None:
    assert mastery_stage(completed=completed, repetitions=reps) == stage


# --- grading ---------------------------------------------------------------------------------

A, B, C, D = (uuid.uuid4() for _ in range(4))


def test_all_or_nothing_grading() -> None:
    assert is_correct([A], [A])
    assert is_correct([B, A], [A, B])
    assert not is_correct([A], [A, B])  # subset
    assert not is_correct([A, B, C], [A, B])  # superset
    assert not is_correct([C], [A])


@pytest.mark.parametrize(
    ("qtype", "selected", "problem"),
    [
        ("single_choice", [A], None),
        ("single_choice", [A, B], "INVALID_SELECTION_COUNT"),
        ("true_false", [A, B], "INVALID_SELECTION_COUNT"),
        ("multi_select", [A, B], None),
        ("multi_select", [A, A], "INVALID_OPTIONS"),
        ("single_choice", [D], "INVALID_OPTIONS"),
    ],
)
def test_selection_validation(qtype: str, selected: list[uuid.UUID], problem: str | None) -> None:
    assert selection_problem(qtype, selected, [A, B, C]) == problem
