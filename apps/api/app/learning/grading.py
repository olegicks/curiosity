"""Server-side answer validation and grading. Pure functions."""

import uuid
from collections.abc import Collection

SINGLE_ANSWER_TYPES = frozenset({"single_choice", "true_false"})


def selection_problem(
    question_type: str, selected: list[uuid.UUID], option_ids: Collection[uuid.UUID]
) -> str | None:
    """Return the error code for an invalid selection, or None when it is acceptable."""
    if len(set(selected)) != len(selected) or not set(selected) <= set(option_ids):
        return "INVALID_OPTIONS"
    if question_type in SINGLE_ANSWER_TYPES and len(selected) != 1:
        return "INVALID_SELECTION_COUNT"
    return None


def is_correct(selected: Collection[uuid.UUID], correct: Collection[uuid.UUID]) -> bool:
    """All-or-nothing: exactly the correct options and nothing else."""
    return set(selected) == set(correct)


def estimate_problem(value: float | None, config: dict[str, float] | None) -> str | None:
    """Estimate questions take a value inside the slider range; others take options."""
    if config is None:
        return "INVALID_OPTIONS" if value is not None else None
    if value is None:
        return "INVALID_VALUE"
    if not config["min"] <= value <= config["max"]:
        return "INVALID_VALUE"
    return None


def estimate_correct(value: float, config: dict[str, float]) -> bool:
    return abs(value - config["answer"]) <= config["tolerance"]
