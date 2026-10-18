"""Content schema, per-lesson rules and loader (docs/spec/11 T-CNT-3)."""

import base64
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from app.config import DEFAULT_CONTENT_DIR
from app.content.loader import content_hash, load_content
from app.content.rules import lesson_problems
from app.content.schema import LessonFile
from app.core.pagination import InvalidCursorError, decode_cursor, encode_cursor
from tests.content_factory import make_lesson, standard_lessons, write_content

TODAY = date(2026, 11, 2)
Mutation = Callable[[dict[str, Any]], None]


def problems_for(data: dict[str, Any]) -> list[str]:
    return lesson_problems(LessonFile.model_validate(data))


def test_valid_lesson_has_no_problems() -> None:
    assert problems_for(make_lesson("anchoring", related=["x"])) == []


def _set(path: str, value: Any) -> Mutation:
    def apply(data: dict[str, Any]) -> None:
        target: Any = data
        *parents, last = path.split(".")
        for part in parents:
            target = target[int(part)] if part.isdigit() else target[part]
        target[int(last) if last.isdigit() else last] = value

    return apply


def _drop_step(step_type: str) -> Mutation:
    def apply(data: dict[str, Any]) -> None:
        data["steps"] = [s for s in data["steps"] if s["type"] != step_type]

    return apply


def _move_hook_last(data: dict[str, Any]) -> None:
    data["steps"].insert(-1, data["steps"].pop(0))


def _drop_recall(data: dict[str, Any]) -> None:
    data["questions"] = [q for q in data["questions"] if q["key"] != "recall-1"][:5]


def _second_summary(data: dict[str, Any]) -> None:
    data["steps"].insert(1, {"type": "summary", "points": ["a", "b"]})


def _recall_step(data: dict[str, Any]) -> None:
    data["steps"].insert(1, {"type": "question", "question_key": "recall-1"})


def _unplaced_lesson_question(data: dict[str, Any]) -> None:
    data["steps"] = [s for s in data["steps"] if s.get("question_key") != "check-2"]


def _duplicate_prompt(data: dict[str, Any]) -> None:
    data["questions"][2]["prompt"] = data["questions"][0]["prompt"]


def _two_true_false(data: dict[str, Any]) -> None:
    for q in data["questions"][2:4]:
        q["type"] = "true_false"
        q["options"] = [
            {"key": "true", "text": "True", "correct": True, "feedback": "Yes."},
            {"key": "false", "text": "False", "correct": False, "feedback": "No."},
        ]


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        (_move_hook_last, "hook step"),
        (_second_summary, "summary step"),
        (_drop_step("misconception"), "misconception"),
        (_drop_step("example"), "1-3 example"),
        (_set("evidence_status", "mixed"), "evidence step is required"),
        (_set("steps.3.source_key", None), "research examples need a source_key"),
        (_set("steps.3.source_key", "src-z"), "not listed in sources"),
        (_set("questions.0.options.1.correct", True), "exactly 1 correct"),
        (
            _set("questions.0.options", make_lesson("x")["questions"][0]["options"][:2]),
            "3-5 options",
        ),
        (_set("questions.0.type", "multi_select"), "multi_select"),
        (_set("questions.0.type", "true_false"), "keyed true/false"),
        (_drop_recall, "at least 4 recall"),
        (_duplicate_prompt, "duplicates a lesson question prompt"),
        (_recall_step, "must reference a lesson-role question"),
        (_unplaced_lesson_question, "not placed in any step"),
        (_set("steps.2.question_key", "nope"), "unknown question"),
        (_two_true_false, "at most one true_false"),
        (_set("related", ["anchoring"]), "cannot reference itself"),
    ],
)
def test_lesson_rule_violations(mutation: Mutation, expected: str) -> None:
    data = make_lesson("anchoring", related=["x"])
    mutation(data)
    problems = problems_for(data)
    assert any(expected in p for p in problems), problems


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        ("last_reviewed_on", None, "last_reviewed_on"),
        ("reviewers", ["Solo Author"], "independent reviewer"),
        ("related", [], "1-4 related"),
        ("sources", [{"key": "src-a"}], "at least 2 sources"),
    ],
)
def test_published_lessons_need_editorial_metadata(field: str, value: Any, expected: str) -> None:
    data = make_lesson("anchoring", related=["x"])
    data[field] = value
    assert any(expected in p for p in problems_for(data))
    data["status"] = "draft"
    assert not any(expected in p for p in problems_for(data))


def test_hook_word_limit() -> None:
    data = make_lesson("anchoring", related=["x"])
    data["steps"][0]["body"] = " ".join(["word"] * 81)
    assert any("hook exceeds" in p for p in problems_for(data))


@pytest.mark.parametrize(
    ("field", "value"),
    [("slug", "Bad Slug"), ("title", "x" * 61), ("estimated_minutes", 11), ("surprise", 1)],
)
def test_schema_rejects_bad_fields(tmp_path: Path, field: str, value: Any) -> None:
    lesson = make_lesson("anchoring")
    lesson[field] = value
    root = write_content(tmp_path, [{**lesson, "slug": "anchoring"}])
    if field == "slug":  # keep the file path valid; the slug inside is what fails
        (root / "psychology/judgment/anchoring.yaml").write_text(
            (root / "psychology/judgment/anchoring.yaml")
            .read_text()
            .replace("slug: anchoring", "slug: Bad Slug")
        )
    content = load_content(root, today=TODAY)
    assert not content.ok
    assert any(field in e for e in content.errors), content.errors


# --- loader / cross-file -----------------------------------------------------------------


def test_standard_content_set_loads(tmp_path: Path) -> None:
    content = load_content(write_content(tmp_path, standard_lessons()), today=TODAY)
    assert content.errors == []
    assert len(content.lessons) == 5


def test_repository_content_is_valid() -> None:
    content = load_content(DEFAULT_CONTENT_DIR, today=TODAY)
    assert content.errors == []


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        (lambda ls: ls[0].update(topic="unknown"), "unknown subject/topic"),
        (lambda ls: ls[0].update(sources=[{"key": "nope"}, {"key": "src-a"}]), "unknown source"),
        (lambda ls: ls[0].update(related=["ghost"]), "unknown related lesson"),
        (
            lambda ls: ls[2].update(slug="anchoring", related=["availability"]),
            "duplicate lesson slug",
        ),
        (
            lambda ls: (
                ls[0].update(prerequisites=["availability"]),
                ls[1].update(prerequisites=["anchoring"]),
            ),
            "prerequisite cycle",
        ),
        (
            lambda ls: ls[0]["steps"][0].update(image={"file": "pic.png", "alt": "A picture"}),
            "missing image",
        ),
    ],
)
def test_cross_file_errors(
    tmp_path: Path, change: Callable[[list[dict[str, Any]]], Any], expected: str
) -> None:
    lessons = standard_lessons()
    change(lessons)
    content = load_content(write_content(tmp_path, lessons), today=TODAY)
    assert any(expected in e for e in content.errors), content.errors


def test_file_location_must_match_slug(tmp_path: Path) -> None:
    root = write_content(tmp_path, standard_lessons())
    (root / "psychology/judgment/anchoring.yaml").rename(root / "psychology/judgment/other.yaml")
    content = load_content(root, today=TODAY)
    assert any("file must live at" in e for e in content.errors)


def test_topic_slugs_must_be_globally_unique(tmp_path: Path) -> None:
    subjects = {
        "subjects": [
            {
                "slug": s,
                "title": s,
                "description": "d",
                "position": i,
                "published": True,
                "topics": [{"slug": "shared", "title": "T", "description": "d", "position": 1}],
            }
            for i, s in enumerate(["one", "two"])
        ]
    }
    content = load_content(write_content(tmp_path, [], subjects=subjects), today=TODAY)
    assert any("unique across all subjects" in e for e in content.errors)


def test_stale_review_and_short_pool_are_warnings(tmp_path: Path) -> None:
    lesson = make_lesson("anchoring", related=["availability"])
    lesson["last_reviewed_on"] = "2025-01-01"
    lesson["questions"] = lesson["questions"][:6]  # 4 recall questions
    other = make_lesson("availability", position=2, related=["anchoring"])
    content = load_content(write_content(tmp_path, [lesson, other]), today=TODAY)
    assert content.errors == []
    assert any("12 months" in w for w in content.warnings)
    assert any("only 4 recall" in w for w in content.warnings)


def test_content_hash_ignores_editorial_metadata() -> None:
    base = LessonFile.model_validate(make_lesson("anchoring"))
    editorial = base.model_copy(
        update={
            "status": "draft",
            "reviewers": ["Someone"],
            "position": 9,
            "last_reviewed_on": None,
        }
    )
    assert content_hash(base) == content_hash(editorial)
    changed = base.model_copy(update={"title": "A different title"})
    assert content_hash(base) != content_hash(changed)


# --- pagination ---------------------------------------------------------------------------


def test_cursor_roundtrip_and_rejects_garbage() -> None:
    key = [1, 2, 3, "abc"]
    assert decode_cursor(encode_cursor(key)) == key
    not_a_list = base64.urlsafe_b64encode(b'{"a": 1}').decode()
    for bad in ["%%%", "bm90IGpzb24", not_a_list, "x" * 600]:
        with pytest.raises(InvalidCursorError):
            decode_cursor(bad)
