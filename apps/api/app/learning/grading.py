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
