"""Recommendation rules (docs/spec/07 §7.8)."""

from app.learning.recommendations import LessonInfo, next_after_completion, rank_lessons

LESSONS = [
    LessonInfo("heuristics", "foundations", ()),
    LessonInfo("anchoring", "judgment", ("heuristics",)),
    LessonInfo("availability", "judgment", ()),
    LessonInfo("framing", "decisions", ()),
    LessonInfo("conformity", "social", ()),
]


def test_curated_order_with_prerequisites_gating() -> None:
    assert rank_lessons(LESSONS, completed=[], interests=[]) == [
        "heuristics",
        "availability",
        "framing",
        "conformity",
    ]
    assert rank_lessons(LESSONS, completed=["heuristics"], interests=[])[0] == "anchoring"


def test_interest_topics_come_first_in_curated_order() -> None:
    ranked = rank_lessons(LESSONS, completed=[], interests=["social", "decisions"])
    assert ranked == ["framing", "conformity", "heuristics", "availability"]


def test_prerequisites_are_ignored_when_nothing_is_eligible() -> None:
    gated = [LessonInfo("a", "t", ("x",)), LessonInfo("b", "t", ("x",))]
    assert rank_lessons(gated, completed=[], interests=[]) == ["a", "b"]


def test_one_related_lesson_is_boosted() -> None:
    ranked = rank_lessons(
        LESSONS,
        completed=["heuristics"],
        interests=[],
        boost_related=["completed-already", "conformity", "framing"],
    )
    assert ranked[:2] == ["conformity", "anchoring"]  # only the first eligible match moves


def test_boost_does_not_bypass_prerequisites() -> None:
    ranked = rank_lessons(LESSONS, completed=[], interests=[], boost_related=["anchoring"])
    assert "anchoring" not in ranked


def test_everything_completed() -> None:
    all_slugs = [lesson.slug for lesson in LESSONS]
    assert rank_lessons(LESSONS, completed=all_slugs, interests=[]) == []
    assert next_after_completion(LESSONS, completed=all_slugs, interests=[], related=[]) is None


def test_next_after_completion_prefers_related_then_ranking() -> None:
    assert (
        next_after_completion(
            LESSONS, completed=["heuristics"], interests=[], related=["framing", "anchoring"]
        )
        == "framing"
    )
    assert (
        next_after_completion(
            LESSONS, completed=["heuristics", "framing"], interests=["social"], related=["framing"]
        )
        == "conformity"
    )
    # unpublished related lessons are skipped
    assert (
        next_after_completion(LESSONS, completed=[], interests=[], related=["draft-only"])
        == "heuristics"
    )
