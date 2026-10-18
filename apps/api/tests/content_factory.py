"""Builds valid content trees for tests; tweak the returned dicts to break rules."""

import copy
import uuid
from pathlib import Path
from typing import Any

import yaml

SUBJECTS: dict[str, Any] = {
    "subjects": [
        {
            "slug": "psychology",
            "title": "Psychology",
            "description": "How people think.",
            "position": 1,
            "published": True,
            "topics": [
                {"slug": "judgment", "title": "Judgment", "description": "D.", "position": 1},
                {"slug": "decisions", "title": "Decisions", "description": "D.", "position": 2},
                {"slug": "social", "title": "Social", "description": "D.", "position": 3},
            ],
        }
    ]
}

SOURCES: dict[str, Any] = {
    "sources": [
        {
            "key": "src-a",
            "type": "journal_article",
            "citation": "Author, A. (2000). A study. Journal, 1(1), 1-2.",
            "doi": "10.0000/a",
            "peer_reviewed": True,
        },
        {
            "key": "src-b",
            "type": "book",
            "citation": "Author, B. (2010). A book. Publisher.",
            "peer_reviewed": False,
        },
    ]
}

FILLER = " ".join(["word"] * 60)


def _single(key: str, role: str, prompt: str) -> dict[str, Any]:
    return {
        "key": key,
        "role": role,
        "type": "single_choice",
        "prompt": prompt,
        "options": [
            {"key": "a", "text": "Right", "correct": True, "feedback": "Because it is right."},
            {"key": "b", "text": "Wrong", "correct": False, "feedback": "Because it is wrong."},
            {"key": "c", "text": "Also wrong", "correct": False, "feedback": "Also wrong."},
        ],
        "explanation": "General explanation.",
    }


def make_lesson(
    slug: str,
    *,
    topic: str = "judgment",
    position: int = 1,
    status: str = "published",
    version: int = 1,
    related: list[str] | None = None,
    lesson_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    published = status == "published"
    return {
        "id": str(lesson_id or uuid.uuid5(uuid.NAMESPACE_URL, slug)),
        "slug": slug,
        "version": version,
        "status": status,
        "subject": "psychology",
        "topic": topic,
        "position": position,
        "title": f"Lesson {slug}",
        "description": "A short description.",
        "learning_objective": "Recognize the thing.",
        "estimated_minutes": 5,
        "evidence_status": "established",
        "last_reviewed_on": "2026-10-01" if published else None,
        "reviewers": ["Author", "Reviewer"] if published else [],
        "prerequisites": [],
        "related": related if related is not None else [],
        "sources": [{"key": "src-a"}, {"key": "src-b"}],
        "steps": [
            {"type": "hook", "body": f"Hook question? {FILLER}"},
            {"type": "explanation", "title": "Idea", "body": f"Explanation. {FILLER}"},
            {"type": "question", "question_key": "check-1"},
            {"type": "example", "kind": "research", "source_key": "src-a", "body": FILLER},
            {"type": "misconception", "myth": "A myth.", "correction": f"Correction. {FILLER}"},
            {"type": "question", "question_key": "check-2"},
            {"type": "summary", "points": ["First point.", "Second point."]},
        ],
        "questions": [
            _single("check-1", "lesson", "Lesson question one?"),
            _single("check-2", "lesson", "Lesson question two?"),
            *[_single(f"recall-{i}", "recall", f"Recall question {i}?") for i in range(1, 6)],
        ],
    }


def write_content(
    root: Path,
    lessons: list[dict[str, Any]],
    *,
    subjects: dict[str, Any] | None = None,
    sources: dict[str, Any] | None = None,
) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "subjects.yaml").write_text(yaml.safe_dump(copy.deepcopy(subjects or SUBJECTS)))
    (root / "sources.yaml").write_text(yaml.safe_dump(copy.deepcopy(sources or SOURCES)))
    for lesson in lessons:
        path = root / lesson["subject"] / lesson["topic"] / f"{lesson['slug']}.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(lesson, sort_keys=False))
    return root


def standard_lessons() -> list[dict[str, Any]]:
    """Three published lessons across two topics, one draft, one retired."""
    return [
        make_lesson("anchoring", topic="judgment", position=1, related=["framing-effect"]),
        make_lesson(
            "availability", topic="judgment", position=2, related=["anchoring", "draft-one"]
        ),
        make_lesson("framing-effect", topic="decisions", position=1, related=["anchoring"]),
        make_lesson("draft-one", topic="decisions", position=2, status="draft"),
        make_lesson("retired-one", topic="social", position=1, status="retired"),
    ]
