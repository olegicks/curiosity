"""SM-2-inspired scheduler ``sm2-curiosity-v1`` (docs/spec/07 §7.3). Pure, no I/O."""

import math
from dataclasses import dataclass, replace
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Protocol

VERSION = "sm2-curiosity-v1"

EF_INITIAL = Decimal("2.50")
EF_MIN = Decimal("1.30")
EF_MAX = Decimal("2.80")
FIRST_INTERVAL = 1
SECOND_INTERVAL = 6
MAX_INTERVAL = 180
FAIL_EF_PENALTY = Decimal("0.20")

QUALITY_FAIL = 1
QUALITY_HARD = 3
QUALITY_GOOD = 4


@dataclass(frozen=True)
class ReviewSchedule:
    ease_factor: Decimal
    interval_days: int
    repetitions: int
    lapses: int
    due_on: date


class Scheduler(Protocol):
    version: str

    def initial_state(self, completed_on: date) -> ReviewSchedule: ...

    def grade(self, *, is_correct: bool, guessed: bool) -> int: ...

    def next_state(self, state: ReviewSchedule, q: int, reviewed_on: date) -> ReviewSchedule: ...


def _clamp_ef(value: Decimal) -> Decimal:
    rounded = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return min(max(rounded, EF_MIN), EF_MAX)


class Sm2Scheduler:
    version = VERSION

    def initial_state(self, completed_on: date) -> ReviewSchedule:
        """State after the first lesson completion: first review tomorrow."""
        return ReviewSchedule(
            ease_factor=EF_INITIAL,
            interval_days=FIRST_INTERVAL,
            repetitions=0,
            lapses=0,
            due_on=completed_on + timedelta(days=FIRST_INTERVAL),
        )

    def grade(self, *, is_correct: bool, guessed: bool) -> int:
        """Map an objectively scored answer to quality q (spec 07 §7.3.3)."""
        if not is_correct:
            return QUALITY_FAIL
        return QUALITY_HARD if guessed else QUALITY_GOOD

    def next_state(self, state: ReviewSchedule, q: int, reviewed_on: date) -> ReviewSchedule:
        if q not in (QUALITY_FAIL, QUALITY_HARD, QUALITY_GOOD):
            raise ValueError(f"unsupported quality {q}")
        if q >= QUALITY_HARD:
            reps = state.repetitions + 1
            if reps == 1:
                interval = SECOND_INTERVAL
            else:  # uses the ease factor *before* this review's update (classic SM-2)
                interval = math.ceil(Decimal(state.interval_days) * state.ease_factor)
            interval = min(max(interval, state.interval_days + 1), MAX_INTERVAL)
            delta = Decimal("0.1") - (5 - q) * (Decimal("0.08") + (5 - q) * Decimal("0.02"))
            return replace(
                state,
                ease_factor=_clamp_ef(state.ease_factor + delta),
                interval_days=interval,
                repetitions=reps,
                due_on=reviewed_on + timedelta(days=interval),
            )
        return replace(
            state,
            ease_factor=_clamp_ef(state.ease_factor - FAIL_EF_PENALTY),
            interval_days=FIRST_INTERVAL,
            repetitions=0,
            lapses=state.lapses + 1,
            due_on=reviewed_on + timedelta(days=FIRST_INTERVAL),
        )


def mastery_stage(*, completed: bool, repetitions: int) -> int:
    """0 = not completed, 1 learned, 2 recalled, 3 understood, 4 retained (spec 07 §7.2)."""
    if not completed:
        return 0
    return min(repetitions, 3) + 1
