"""Deterministic lesson recommendations (docs/spec/07 §7.8). Pure functions."""

from collections.abc import Collection, Sequence
from dataclasses import dataclass

RECOMMENDED_COUNT = 4


@dataclass(frozen=True)
class LessonInfo:
    slug: str
    topic: str
    prerequisites: tuple[str, ...]  # published prerequisites only


def rank_lessons(
    lessons: Sequence[LessonInfo],
    *,
    completed: Collection[str],
    interests: Collection[str],
    boost_related: Sequence[str] = (),
) -> list[str]:
    """Order uncompleted lessons for this learner.

    ``lessons`` must already be in curated order (subject, topic, lesson position).
    1. candidates: not completed
    2. eligible: all prerequisites completed (if none are, prerequisites are ignored)
    3. interest topics first, curated order otherwise (stable sort)
    4. the first eligible lesson related to the most recently completed one moves to
       the front (at most one boost)
    """
    done = set(completed)
    candidates = [lesson for lesson in lessons if lesson.slug not in done]
    eligible = [c for c in candidates if all(p in done for p in c.prerequisites)] or candidates
    wanted = set(interests)
    ordered = sorted(eligible, key=lambda c: 0 if wanted and c.topic in wanted else 1)
    slugs = [c.slug for c in ordered]
    for slug in boost_related:
        if slug in slugs:
            slugs.remove(slug)
            slugs.insert(0, slug)
            break
    return slugs


def next_after_completion(
    lessons: Sequence[LessonInfo],
    *,
    completed: Collection[str],
    interests: Collection[str],
    related: Sequence[str],
) -> str | None:
    """First uncompleted related lesson, else today's lesson recomputed, else none."""
    done = set(completed)
    published = {lesson.slug for lesson in lessons}
    for slug in related:
        if slug in published and slug not in done:
            return slug
    ranked = rank_lessons(lessons, completed=done, interests=interests, boost_related=related)
    return ranked[0] if ranked else None
