"""Estimate questions: content rules, hashing and grading (D-18)."""

from typing import Any

import pytest

from app.content.rules import lesson_problems
from app.content.schema import LessonFile
from app.learning.grading import estimate_correct, estimate_problem
from tests.content_factory import make_lesson

CONFIG: dict[str, Any] = {"min": 0, "max": 8000, "step": 100, "answer": 3700, "tolerance": 600}


def estimate_question(**overrides: Any) -> dict[str, Any]:
    question: dict[str, Any] = {
        "key": "check-2",
        "role": "lesson",
        "type": "estimate",
        "prompt": "How long is the Mississippi?",
        "estimate": {**CONFIG, "unit": "km", "anchor": 7000},
        "explanation": "About 3,700 km.",
    }
    question.update(overrides)
    return question


def lesson_with(question: dict[str, Any]) -> LessonFile:
    data = make_lesson("anchoring", related=["x"])
    data["questions"][1] = question
    return LessonFile.model_validate(data)


def test_valid_estimate_question() -> None:
    assert lesson_problems(lesson_with(estimate_question())) == []


OPTION = {"key": "a", "text": "A", "correct": True, "feedback": "F."}


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"estimate": None}, "needs an estimate block"),
        ({"role": "recall"}, "lesson questions only"),
        ({"options": [OPTION, {**OPTION, "key": "b"}]}, "have no options"),
        ({"estimate": {**CONFIG, "unit": "km", "answer": 9000}}, "answer must be within"),
        ({"estimate": {**CONFIG, "unit": "km", "anchor": -5}}, "anchor must be within"),
        ({"estimate": {**CONFIG, "unit": "km", "min": 9000}}, "min must be below max"),
        ({"estimate": {**CONFIG, "unit": "km", "tolerance": 9000}}, "must fit the range"),
    ],
)
def test_estimate_rule_violations(overrides: dict[str, Any], expected: str) -> None:
    problems = lesson_problems(lesson_with(estimate_question(**overrides)))
    assert any(expected in p for p in problems), problems


def test_choice_questions_reject_an_estimate_block() -> None:
    data = make_lesson("anchoring", related=["x"])
    data["questions"][0]["estimate"] = {**CONFIG, "unit": "km"}
    problems = lesson_problems(LessonFile.model_validate(data))
    assert any("only estimate questions" in p for p in problems)


def _questions(lesson: LessonFile) -> list[dict[str, Any]]:
    questions = lesson.content_payload()["questions"]
    assert isinstance(questions, list)
    return questions


def test_hash_payload_omits_unset_estimate() -> None:
    plain = LessonFile.model_validate(make_lesson("anchoring", related=["x"]))
    assert all("estimate" not in q for q in _questions(plain))
    assert any("estimate" in q for q in _questions(lesson_with(estimate_question())))


def test_estimate_grading() -> None:
    assert estimate_problem(None, None) is None
    assert estimate_problem(5.0, None) == "INVALID_OPTIONS"
    assert estimate_problem(None, CONFIG) == "INVALID_VALUE"
    assert estimate_problem(8001, CONFIG) == "INVALID_VALUE"
    assert estimate_problem(4000, CONFIG) is None
    assert estimate_correct(4300, CONFIG)
    assert estimate_correct(3100, CONFIG)
    assert not estimate_correct(5600, CONFIG)
