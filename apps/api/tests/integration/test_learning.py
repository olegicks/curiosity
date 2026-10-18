"""Lesson attempts, grading, completion and progress (docs/spec/11 T-LRN-*)."""

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.content.models import AnswerOption, Question
from app.learning.models import LessonAttempt, UserLessonProgress
from app.reviews.models import ReviewState
from tests.conftest import Importer
from tests.content_factory import standard_lessons

pytestmark = pytest.mark.db


@pytest.fixture
def lessons(run_import: Importer) -> None:
    content = standard_lessons()
    # make one lesson question multi-select to cover all-or-nothing grading
    content[0]["questions"][1].update(
        type="multi_select",
        options=[
            {"key": "a", "text": "One", "correct": True, "feedback": "Yes, one."},
            {"key": "b", "text": "Two", "correct": True, "feedback": "Yes, two."},
            {"key": "c", "text": "Three", "correct": False, "feedback": "Not three."},
            {"key": "d", "text": "Four", "correct": False, "feedback": "Not four."},
        ],
    )
    run_import(content)


def start(client: TestClient, auth: dict[str, str], slug: str = "anchoring", **body: Any) -> Any:
    return client.post(f"/v1/lessons/{slug}/attempts", headers=auth, json=body or None)


def option_ids(db: Session, question_id: str, *, correct: bool) -> list[str]:
    return [
        str(o.id)
        for o in db.scalars(
            select(AnswerOption)
            .where(
                AnswerOption.question_id == uuid.UUID(question_id),
                AnswerOption.is_correct.is_(correct),
            )
            .order_by(AnswerOption.position)
        )
    ]


def answer(
    client: TestClient, auth: dict[str, str], attempt_id: str, question_id: str, ids: list[str]
) -> Any:
    return client.post(
        f"/v1/attempts/{attempt_id}/answers",
        headers=auth,
        json={"question_id": question_id, "selected_option_ids": ids},
    )


def answer_all(
    client: TestClient, auth: dict[str, str], db: Session, body: dict[str, Any], *, correct: bool
) -> None:
    attempt_id = body["attempt"]["id"]
    for q in body["content"]["questions"]:
        right = option_ids(db, q["id"], correct=True)
        ids = right if correct else option_ids(db, q["id"], correct=False)[:1]
        assert answer(client, auth, attempt_id, q["id"], ids).status_code == 201


def complete(client: TestClient, auth: dict[str, str], attempt_id: str) -> Any:
    return client.post(f"/v1/attempts/{attempt_id}/complete", headers=auth)


def finish_lesson(
    client: TestClient, auth: dict[str, str], db: Session, slug: str = "anchoring"
) -> Any:
    body = start(client, auth, slug).json()
    answer_all(client, auth, db, body, correct=True)
    return complete(client, auth, body["attempt"]["id"])


# --- start / resume ---------------------------------------------------------------------------


@pytest.mark.usefixtures("lessons")
def test_start_then_resume_same_attempt(db_client: TestClient, auth: dict[str, str]) -> None:
    first = start(db_client, auth)
    assert first.status_code == 201
    body = first.json()
    assert body["resumed"] is False
    assert body["attempt"]["status"] == "in_progress"
    assert body["attempt"]["is_revisit"] is False
    assert len(body["content"]["questions"]) == 2

    again = start(db_client, auth)
    assert again.status_code == 200
    assert again.json()["resumed"] is True
    assert again.json()["attempt"]["id"] == body["attempt"]["id"]


@pytest.mark.usefixtures("lessons")
def test_restart_abandons_open_attempt(
    db_client: TestClient, auth: dict[str, str], db_session: Session
) -> None:
    first_body = start(db_client, auth).json()
    first = first_body["attempt"]["id"]
    restarted = start(db_client, auth, restart=True)
    assert restarted.status_code == 201
    assert restarted.json()["attempt"]["id"] != first
    old = db_session.get(LessonAttempt, uuid.UUID(first))
    assert old is not None
    assert old.status == "abandoned"
    assert complete(db_client, auth, first).json()["error"]["code"] == "ATTEMPT_NOT_OPEN"
    q = first_body["content"]["questions"][0]
    late = answer(db_client, auth, first, q["id"], [q["options"][0]["id"]])
    assert late.status_code == 409
    assert late.json()["error"]["code"] == "ATTEMPT_NOT_OPEN"


@pytest.mark.usefixtures("lessons")
@pytest.mark.parametrize("slug", ["draft-one", "retired-one", "nope"])
def test_cannot_start_unpublished_lessons(
    db_client: TestClient, auth: dict[str, str], slug: str
) -> None:
    response = start(db_client, auth, slug)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "LESSON_NOT_FOUND"


# --- answers ----------------------------------------------------------------------------------


@pytest.mark.usefixtures("lessons")
def test_answers_are_graded_on_the_server(
    db_client: TestClient, auth: dict[str, str], db_session: Session
) -> None:
    body = start(db_client, auth).json()
    attempt_id = body["attempt"]["id"]
    single, multi = body["content"]["questions"]

    wrong = answer(
        db_client,
        auth,
        attempt_id,
        single["id"],
        option_ids(db_session, single["id"], correct=False)[:1],
    )
    assert wrong.status_code == 201
    result = wrong.json()
    assert result["is_correct"] is False
    assert result["replayed"] is False
    assert result["correct_option_ids"] == option_ids(db_session, single["id"], correct=True)
    assert {f["option_id"] for f in result["option_feedback"]} == {
        o["id"] for o in single["options"]
    }
    assert [f["option_id"] for f in result["option_feedback"]] == [
        o["id"] for o in single["options"]
    ]  # same order the learner saw
    assert result["explanation"] == "General explanation."

    right_multi = option_ids(db_session, multi["id"], correct=True)
    subset = answer(db_client, auth, attempt_id, multi["id"], right_multi[:1])
    assert subset.json()["is_correct"] is False  # all-or-nothing


@pytest.mark.usefixtures("lessons")
def test_multi_select_needs_exactly_the_correct_set(
    db_client: TestClient, auth: dict[str, str], db_session: Session
) -> None:
    body = start(db_client, auth).json()
    multi = body["content"]["questions"][1]
    right = option_ids(db_session, multi["id"], correct=True)
    response = answer(db_client, auth, body["attempt"]["id"], multi["id"], list(reversed(right)))
    assert response.json()["is_correct"] is True


@pytest.mark.usefixtures("lessons")
def test_first_answer_is_final(
    db_client: TestClient, auth: dict[str, str], db_session: Session
) -> None:
    body = start(db_client, auth).json()
    attempt_id = body["attempt"]["id"]
    q = body["content"]["questions"][0]
    wrong = option_ids(db_session, q["id"], correct=False)[:1]
    answer(db_client, auth, attempt_id, q["id"], wrong)
    replay = answer(
        db_client, auth, attempt_id, q["id"], option_ids(db_session, q["id"], correct=True)
    )
    assert replay.status_code == 200
    assert replay.json()["replayed"] is True
    assert replay.json()["is_correct"] is False
    assert replay.json()["selected_option_ids"] == wrong

    resumed = start(db_client, auth).json()
    assert [a["question_id"] for a in resumed["attempt"]["answers"]] == [q["id"]]


@pytest.mark.usefixtures("lessons")
def test_answer_validation(
    db_client: TestClient, auth: dict[str, str], db_session: Session
) -> None:
    body = start(db_client, auth).json()
    attempt_id = body["attempt"]["id"]
    single, multi = body["content"]["questions"]
    single_options = [o["id"] for o in single["options"]]
    recall = db_session.scalar(
        select(Question.id).where(
            Question.role == "recall",
            Question.lesson_version_id == uuid.UUID(body["attempt"]["lesson_version_id"]),
        )
    )

    cases = [
        (single["id"], single_options[:2], "INVALID_SELECTION_COUNT"),
        (single["id"], [single_options[0], single_options[0]], "INVALID_OPTIONS"),
        (single["id"], [multi["options"][0]["id"]], "INVALID_OPTIONS"),
        (str(recall), single_options[:1], "QUESTION_NOT_IN_ATTEMPT"),
        (str(uuid.uuid4()), single_options[:1], "QUESTION_NOT_IN_ATTEMPT"),
    ]
    for question_id, ids, code in cases:
        response = answer(db_client, auth, attempt_id, question_id, ids)
        assert response.status_code == 422, (code, response.text)
        assert response.json()["error"]["code"] == code
    empty = answer(db_client, auth, attempt_id, single["id"], [])
    assert empty.json()["error"]["code"] == "VALIDATION_ERROR"


# --- completion ------------------------------------------------------------------------------


@pytest.mark.usefixtures("lessons")
def test_completion_requires_every_answer(
    db_client: TestClient, auth: dict[str, str], db_session: Session
) -> None:
    body = start(db_client, auth).json()
    first, second = body["content"]["questions"]
    answer(
        db_client,
        auth,
        body["attempt"]["id"],
        first["id"],
        option_ids(db_session, first["id"], correct=True),
    )
    response = complete(db_client, auth, body["attempt"]["id"])
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ATTEMPT_INCOMPLETE"
    assert response.json()["error"]["details"] == [{"question_id": second["id"]}]


@pytest.mark.usefixtures("lessons")
def test_completion_updates_progress_and_schedules_review_exactly_once(
    db_client: TestClient, auth: dict[str, str], db_session: Session
) -> None:
    body = start(db_client, auth).json()
    attempt_id = body["attempt"]["id"]
    answer_all(db_client, auth, db_session, body, correct=True)

    done = complete(db_client, auth, attempt_id)
    assert done.status_code == 200
    summary = done.json()
    assert summary["attempt"] == {
        "id": attempt_id,
        "status": "completed",
        "correct_first_try": 2,
        "question_count": 2,
        "is_first_completion": True,
    }
    assert summary["first_review_on"] == "2026-11-03"
    assert summary["replayed"] is False
    assert summary["next_lesson"]["slug"] == "framing-effect"  # first related lesson

    replay = complete(db_client, auth, attempt_id)
    assert replay.status_code == 200
    assert replay.json() == {**summary, "replayed": True}

    states = db_session.scalars(select(ReviewState)).all()
    assert len(states) == 1
    assert states[0].due_on.isoformat() == "2026-11-03"
    assert states[0].repetitions == 0
    progress = db_session.scalars(select(UserLessonProgress)).one()
    assert progress.completion_count == 1
    assert progress.first_attempt_score == 2

    # every question is answered by now, so resubmitting is a harmless replay
    after = answer(
        db_client, auth, attempt_id, body["content"]["questions"][0]["id"], [str(uuid.uuid4())]
    )
    assert after.status_code == 200
    assert after.json()["replayed"] is True


@pytest.mark.usefixtures("lessons")
def test_first_review_uses_the_users_local_date(
    db_client: TestClient, auth: dict[str, str], db_session: Session
) -> None:
    db_client.patch("/v1/me/preferences", headers=auth, json={"timezone": "Pacific/Auckland"})
    done = finish_lesson(db_client, auth, db_session)  # 12:00 UTC = 01:00 next day in Auckland
    assert done.json()["first_review_on"] == "2026-11-04"


@pytest.mark.usefixtures("lessons")
def test_revisit_does_not_reschedule_or_count_as_first(
    db_client: TestClient, auth: dict[str, str], db_session: Session
) -> None:
    finish_lesson(db_client, auth, db_session)
    state_before = db_session.scalars(select(ReviewState)).one()
    due_before = state_before.due_on

    body = start(db_client, auth).json()
    assert body["attempt"]["is_revisit"] is True
    answer_all(db_client, auth, db_session, body, correct=False)
    done = complete(db_client, auth, body["attempt"]["id"]).json()
    assert done["attempt"]["is_first_completion"] is False
    assert done["attempt"]["correct_first_try"] == 0
    assert done["first_review_on"] is None

    db_session.expire_all()
    assert db_session.scalars(select(ReviewState)).one().due_on == due_before
    progress = db_session.scalars(select(UserLessonProgress)).one()
    assert progress.completion_count == 2
    assert progress.first_attempt_score == 2


@pytest.mark.usefixtures("lessons")
def test_lesson_cards_show_real_progress(
    db_client: TestClient, auth: dict[str, str], db_session: Session
) -> None:
    started = start(db_client, auth, "availability").json()["attempt"]["id"]
    finish_lesson(db_client, auth, db_session, "anchoring")

    items = {
        i["slug"]: i["progress"] for i in db_client.get("/v1/lessons", headers=auth).json()["items"]
    }
    assert items["anchoring"]["status"] == "completed"
    assert items["anchoring"]["mastery_stage"] == 1
    assert items["anchoring"]["next_review_on"] == "2026-11-03"
    assert items["availability"]["status"] == "started"
    assert items["availability"]["in_progress_attempt_id"] == started
    assert items["framing-effect"]["status"] == "not_started"

    def slugs(progress: str) -> list[str]:
        page = db_client.get("/v1/lessons", headers=auth, params={"progress": progress}).json()
        return [i["slug"] for i in page["items"]]

    assert slugs("completed") == ["anchoring"]
    assert slugs("in_progress") == ["availability"]
    assert slugs("not_started") == ["framing-effect"]


@pytest.mark.usefixtures("lessons")
def test_next_lesson_skips_completed(
    db_client: TestClient, auth: dict[str, str], db_session: Session
) -> None:
    finish_lesson(db_client, auth, db_session, "framing-effect")  # related: anchoring
    done = finish_lesson(db_client, auth, db_session, "anchoring")  # related: framing (done)
    assert done.json()["next_lesson"]["slug"] == "availability"  # curated order fallback
    last = finish_lesson(db_client, auth, db_session, "availability")
    assert last.json()["next_lesson"] is None


# --- version pinning ---------------------------------------------------------------------------


def test_attempt_stays_on_its_version_after_a_revision(
    run_import: Importer, db_client: TestClient, auth: dict[str, str], db_session: Session
) -> None:
    content = standard_lessons()
    run_import(content)
    body = start(db_client, auth).json()
    v1 = body["attempt"]["lesson_version_id"]

    content[0].update(version=2)
    content[0]["questions"][0]["prompt"] = "Revised lesson question one?"
    run_import(content)

    resumed = db_client.get(f"/v1/attempts/{body['attempt']['id']}", headers=auth).json()
    assert resumed["attempt"]["lesson_version_id"] == v1
    assert resumed["content"]["questions"][0]["prompt"] == "Lesson question one?"
    answer_all(db_client, auth, db_session, body, correct=True)
    assert complete(db_client, auth, body["attempt"]["id"]).status_code == 200

    fresh = start(db_client, auth).json()
    assert fresh["attempt"]["lesson_version_id"] != v1
    assert fresh["content"]["questions"][0]["prompt"] == "Revised lesson question one?"


# --- isolation and deletion ---------------------------------------------------------------


@pytest.mark.usefixtures("lessons")
def test_attempts_are_private(
    db_client: TestClient, auth: dict[str, str], db_session: Session
) -> None:
    body = start(db_client, auth).json()
    attempt_id = body["attempt"]["id"]
    q = body["content"]["questions"][0]
    other_tokens = db_client.post("/v1/auth/guest", json={}).json()["tokens"]
    other = {"Authorization": f"Bearer {other_tokens['access_token']}"}

    assert db_client.get(f"/v1/attempts/{attempt_id}", headers=other).status_code == 404
    ids = option_ids(db_session, q["id"], correct=True)
    assert answer(db_client, other, attempt_id, q["id"], ids).status_code == 404
    assert complete(db_client, other, attempt_id).status_code == 404
    assert db_client.get(f"/v1/attempts/{uuid.uuid4()}", headers=auth).status_code == 404
    # the owner's attempt is untouched
    assert (
        db_client.get(f"/v1/attempts/{attempt_id}", headers=auth).json()["attempt"]["answers"] == []
    )


@pytest.mark.usefixtures("lessons")
def test_account_deletion_removes_learning_data(
    db_client: TestClient, auth: dict[str, str], db_session: Session
) -> None:
    finish_lesson(db_client, auth, db_session)
    db_client.request("DELETE", "/v1/me", headers=auth, json={"confirm": "DELETE"})
    db_session.expire_all()
    for model in (LessonAttempt, UserLessonProgress, ReviewState):
        assert db_session.scalar(select(func.count()).select_from(model)) == 0
