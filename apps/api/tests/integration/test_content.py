"""Importer, content endpoints and topic interests against PostgreSQL (T-CNT-1/2/4)."""

import json
import uuid
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.content.importer import ContentImportError, ImportSummary, import_content
from app.content.loader import load_content
from app.content.models import Lesson, LessonVersion, Question
from app.core.clock import FixedClock
from app.users.models import UserTopicInterest
from tests.content_factory import make_lesson, standard_lessons, write_content

pytestmark = pytest.mark.db

TODAY = date(2026, 11, 2)
Importer = Callable[..., ImportSummary]


@pytest.fixture
def run_import(db_session: Session, clock: FixedClock, tmp_path: Path) -> Importer:
    counter = iter(range(1000))

    def run(lessons: list[dict[str, Any]], **kwargs: Any) -> ImportSummary:
        root = write_content(tmp_path / f"content-{next(counter)}", lessons)
        content = load_content(root, today=TODAY)
        assert content.errors == []
        return import_content(db_session, content, now=clock.now(), **kwargs)

    return run


@pytest.fixture
def auth(db_client: TestClient) -> dict[str, str]:
    tokens = db_client.post("/v1/auth/guest", json={}).json()["tokens"]
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def lesson_row(db: Session, slug: str) -> Lesson:
    lesson = db.scalar(select(Lesson).where(Lesson.slug == slug))
    assert lesson is not None
    return lesson


# --- importer ------------------------------------------------------------------------------


def test_import_is_idempotent(run_import: Importer, db_session: Session) -> None:
    first = run_import(standard_lessons())
    assert sorted(first.created) == [
        "anchoring",
        "availability",
        "draft-one",
        "framing-effect",
        "retired-one",
    ]
    second = run_import(standard_lessons())
    assert second.created == []
    assert second.new_versions == []
    assert len(second.unchanged) == 5
    assert db_session.scalar(select(func.count()).select_from(LessonVersion)) == 5


def test_changed_content_without_version_bump_fails_atomically(
    run_import: Importer, db_session: Session
) -> None:
    run_import(standard_lessons())
    lessons = standard_lessons()
    lessons[0]["title"] = "Changed title"
    lessons.append(make_lesson("brand-new", topic="social", position=5, related=["anchoring"]))
    with pytest.raises(ContentImportError, match="1 import error"):
        run_import(lessons)
    assert db_session.scalar(select(Lesson).where(Lesson.slug == "brand-new")) is None


def test_version_bump_creates_new_version_and_keeps_old(
    run_import: Importer, db_session: Session
) -> None:
    run_import(standard_lessons())
    old_version_id = lesson_row(db_session, "anchoring").current_version_id
    lessons = standard_lessons()
    lessons[0].update(title="Anchoring, revised", version=2)
    summary = run_import(lessons)
    assert summary.new_versions == ["anchoring v2"]
    lesson = lesson_row(db_session, "anchoring")
    assert lesson.current_version_id != old_version_id
    assert db_session.get(LessonVersion, old_version_id) is not None
    current = db_session.get(LessonVersion, lesson.current_version_id)
    assert current is not None
    assert current.title == "Anchoring, revised"


def test_version_cannot_go_backwards(run_import: Importer) -> None:
    lessons = standard_lessons()
    lessons[0]["version"] = 2
    run_import(lessons)
    lessons[0].update(version=1, title="Older")
    with pytest.raises(ContentImportError) as excinfo:
        run_import(lessons)
    assert "older than imported" in excinfo.value.errors[0]


def test_slug_is_fixed_for_a_lesson_id(run_import: Importer) -> None:
    run_import(standard_lessons())
    lessons = standard_lessons()
    lessons[4]["slug"] = "retired-renamed"  # same id as retired-one
    with pytest.raises(ContentImportError) as excinfo:
        run_import(lessons)
    assert "slugs are fixed" in excinfo.value.errors[0]


def test_draft_overwrite_only_when_allowed(run_import: Importer, db_session: Session) -> None:
    run_import(standard_lessons())
    lessons = standard_lessons()
    lessons[3]["title"] = "Draft, edited"
    with pytest.raises(ContentImportError):
        run_import(lessons)
    summary = run_import(lessons, allow_draft_overwrite=True)
    assert summary.new_versions == ["draft-one v1 (draft overwritten)"]
    questions = db_session.scalar(
        select(func.count())
        .select_from(Question)
        .join(LessonVersion, LessonVersion.id == Question.lesson_version_id)
        .join(Lesson, Lesson.id == LessonVersion.lesson_id)
        .where(Lesson.slug == "draft-one")
    )
    assert questions == 7


def test_publishing_a_draft_needs_no_version_bump(
    run_import: Importer, db_session: Session, clock: FixedClock
) -> None:
    run_import(standard_lessons())
    lessons = standard_lessons()
    lessons[3].update(
        status="published",
        reviewers=["Author", "Reviewer"],
        last_reviewed_on="2026-11-01",
        related=["anchoring"],
    )
    run_import(lessons)
    lesson = lesson_row(db_session, "draft-one")
    assert lesson.status == "published"
    version = db_session.get(LessonVersion, lesson.current_version_id)
    assert version is not None
    assert version.published_at == clock.now()
    assert version.reviewers == ["Author", "Reviewer"]


# --- content endpoints ------------------------------------------------------------------------


def test_subjects_list_topics_with_published_counts(
    run_import: Importer, db_client: TestClient, auth: dict[str, str]
) -> None:
    run_import(standard_lessons())
    body = db_client.get("/v1/subjects", headers=auth).json()
    topics = {t["slug"]: t["lesson_count"] for t in body["items"][0]["topics"]}
    assert topics == {"judgment": 2, "decisions": 1, "social": 0}


def test_lessons_list_only_published_in_curated_order(
    run_import: Importer, db_client: TestClient, auth: dict[str, str]
) -> None:
    run_import(standard_lessons())
    body = db_client.get("/v1/lessons", headers=auth).json()
    assert [i["slug"] for i in body["items"]] == ["anchoring", "availability", "framing-effect"]
    assert body["next_cursor"] is None
    first = body["items"][0]
    assert first["topic"] == {"slug": "judgment", "title": "Judgment"}
    assert first["progress"]["status"] == "not_started"


def test_lessons_pagination_and_filters(
    run_import: Importer, db_client: TestClient, auth: dict[str, str]
) -> None:
    run_import(standard_lessons())
    seen: list[str] = []
    cursor = None
    while True:
        params: dict[str, Any] = {"limit": 1, **({"cursor": cursor} if cursor else {})}
        page = db_client.get("/v1/lessons", headers=auth, params=params).json()
        seen += [i["slug"] for i in page["items"]]
        cursor = page["next_cursor"]
        if cursor is None:
            break
    assert seen == ["anchoring", "availability", "framing-effect"]

    by_topic = db_client.get("/v1/lessons", headers=auth, params={"topic": "decisions"}).json()
    assert [i["slug"] for i in by_topic["items"]] == ["framing-effect"]
    completed = db_client.get("/v1/lessons", headers=auth, params={"progress": "completed"})
    assert completed.json()["items"] == []
    assert db_client.get("/v1/lessons", headers=auth, params={"cursor": "%%%"}).status_code == 422
    assert db_client.get("/v1/lessons", headers=auth, params={"limit": 101}).status_code == 422
    assert db_client.get("/v1/lessons").status_code == 401


def _all_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {k for v in value.values() for k in _all_keys(v)}
    if isinstance(value, list):
        return {k for v in value for k in _all_keys(v)}
    return set()


def test_lesson_detail_never_leaks_answers_or_recall_questions(
    run_import: Importer, db_client: TestClient, auth: dict[str, str]
) -> None:
    run_import(standard_lessons())
    response = db_client.get("/v1/lessons/availability", headers=auth)
    assert response.status_code == 200
    body = response.json()
    assert not _all_keys(body) & {"is_correct", "correct", "feedback", "role"}
    assert "Recall question" not in json.dumps(body)
    assert "General explanation" not in json.dumps(body)

    content = body["content"]
    for question in content["questions"]:
        assert set(question) == {"id", "type", "prompt", "options"}
        assert all(set(option) == {"id", "text"} for option in question["options"])
    assert len(content["questions"]) == 2
    question_ids = {q["id"] for q in content["questions"]}
    step_ids = {s["question_id"] for s in content["steps"] if s["type"] == "question"}
    assert step_ids == question_ids
    assert [s["key"] for s in content["sources"]] == ["src-a", "src-b"]
    # related lists only published lessons (draft-one is filtered out)
    assert [r["slug"] for r in body["lesson"]["related"]] == ["anchoring"]
    assert content["related"] == body["lesson"]["related"]


def test_option_order_is_stable_per_user(
    run_import: Importer, db_client: TestClient, auth: dict[str, str]
) -> None:
    run_import(standard_lessons())

    def order() -> list[str]:
        body = db_client.get("/v1/lessons/anchoring", headers=auth).json()
        return [o["id"] for q in body["content"]["questions"] for o in q["options"]]

    assert order() == order()


@pytest.mark.parametrize("slug", ["draft-one", "retired-one", "no-such-lesson", "BAD SLUG"])
def test_unpublished_or_unknown_lessons_are_not_found(
    run_import: Importer, db_client: TestClient, auth: dict[str, str], slug: str
) -> None:
    run_import(standard_lessons())
    response = db_client.get(f"/v1/lessons/{slug}", headers=auth)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "LESSON_NOT_FOUND"


def test_retiring_a_lesson_hides_it(
    run_import: Importer, db_client: TestClient, auth: dict[str, str]
) -> None:
    run_import(standard_lessons())
    lessons = standard_lessons()
    lessons[2]["status"] = "retired"
    summary = run_import(lessons)
    assert summary.retired == ["framing-effect"]
    assert db_client.get("/v1/lessons/framing-effect", headers=auth).status_code == 404


# --- topic interests ----------------------------------------------------------------------------


def test_interest_topics_round_trip(
    run_import: Importer, db_client: TestClient, auth: dict[str, str]
) -> None:
    run_import(standard_lessons())
    response = db_client.patch(
        "/v1/me/preferences",
        headers=auth,
        json={"interest_topics": ["social", "judgment", "social"]},
    )
    assert response.status_code == 200
    assert response.json()["interest_topics"] == ["judgment", "social"]  # curated order

    replaced = db_client.patch(
        "/v1/me/preferences", headers=auth, json={"interest_topics": ["decisions"]}
    )
    assert replaced.json()["interest_topics"] == ["decisions"]
    cleared = db_client.patch("/v1/me/preferences", headers=auth, json={"interest_topics": []})
    assert cleared.json()["interest_topics"] == []
    untouched = db_client.patch("/v1/me/preferences", headers=auth, json={"daily_xp_goal": 60})
    assert untouched.json()["interest_topics"] == []


def test_unknown_interest_topic_is_rejected_without_changes(
    run_import: Importer, db_client: TestClient, auth: dict[str, str]
) -> None:
    run_import(standard_lessons())
    db_client.patch("/v1/me/preferences", headers=auth, json={"interest_topics": ["judgment"]})
    response = db_client.patch(
        "/v1/me/preferences", headers=auth, json={"interest_topics": ["judgment", "astrology"]}
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "UNKNOWN_TOPIC"
    assert response.json()["error"]["details"][0]["value"] == "astrology"
    me = db_client.get("/v1/me", headers=auth).json()
    assert me["preferences"]["interest_topics"] == ["judgment"]


def test_account_deletion_removes_interests(
    run_import: Importer, db_client: TestClient, auth: dict[str, str], db_session: Session
) -> None:
    run_import(standard_lessons())
    db_client.patch("/v1/me/preferences", headers=auth, json={"interest_topics": ["judgment"]})
    user_id = uuid.UUID(db_client.get("/v1/me", headers=auth).json()["user"]["id"])
    db_client.request("DELETE", "/v1/me", headers=auth, json={"confirm": "DELETE"})
    db_session.expire_all()
    count = db_session.scalar(
        select(func.count())
        .select_from(UserTopicInterest)
        .where(UserTopicInterest.user_id == user_id)
    )
    assert count == 0
