"""GET /v1/discover and completion's next lesson (docs/spec/02 §2.5, 07 §7.8, AC-DISC-*)."""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.clock import FixedClock
from tests.conftest import Importer
from tests.content_factory import make_lesson, standard_lessons
from tests.helpers import Learner, complete_lesson, correct_ids

pytestmark = pytest.mark.db


@pytest.fixture
def learner(db_client: TestClient, clock: FixedClock, run_import: Importer) -> Learner:
    run_import(standard_lessons())
    return Learner(db_client, clock)


def discover(learner: Learner) -> dict[str, Any]:
    response = learner.get("/v1/discover")
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def slugs(lessons: list[dict[str, Any]]) -> list[str]:
    return [lesson["slug"] for lesson in lessons]


def set_interests(learner: Learner, topics: list[str]) -> None:
    response = learner.client.patch(
        "/v1/me/preferences", headers=learner.headers, json={"interest_topics": topics}
    )
    assert response.status_code == 200


def test_new_learner_starts_with_todays_lesson(learner: Learner) -> None:
    body = discover(learner)
    assert body["local_date"] == "2026-11-02"
    assert body["primary_action"]["type"] == "start_lesson"
    assert body["primary_action"]["lesson"]["slug"] == "anchoring"
    assert body["primary_action"]["review"] is None
    assert body["todays_lesson"]["slug"] == "anchoring"
    assert slugs(body["recommended"]) == ["availability", "framing-effect"]
    assert body["progress"] == {"lessons_total": 3, "completed": 0, "understood": 0}
    assert body["xp"] == {"today": 0, "goal": 20, "total": 0}
    assert body["streak"]["current"] == 0
    assert body["reviews_due"] == 0


def test_interests_reorder_recommendations(learner: Learner) -> None:
    set_interests(learner, ["decisions"])
    body = discover(learner)
    assert body["todays_lesson"]["slug"] == "framing-effect"
    assert slugs(body["recommended"]) == ["anchoring", "availability"]


def test_prerequisites_hold_lessons_back(
    db_client: TestClient, clock: FixedClock, run_import: Importer, db_session: Session
) -> None:
    lessons = standard_lessons()
    lessons[0]["prerequisites"] = ["framing-effect"]  # anchoring needs framing-effect first
    run_import(lessons)
    learner = Learner(db_client, clock)
    body = discover(learner)
    assert body["todays_lesson"]["slug"] == "availability"
    assert slugs(body["recommended"]) == ["framing-effect"]

    complete_lesson(learner, db_session, "framing-effect")
    # framing-effect's related lesson is anchoring, now eligible and boosted
    assert discover(learner)["todays_lesson"]["slug"] == "anchoring"


def test_last_completed_lesson_boosts_a_related_one(learner: Learner, db_session: Session) -> None:
    complete_lesson(learner, db_session, "anchoring")  # related: framing-effect
    body = discover(learner)
    assert body["todays_lesson"]["slug"] == "framing-effect"
    assert slugs(body["recommended"]) == ["availability"]
    assert body["progress"]["completed"] == 1


def test_open_attempt_becomes_continue(learner: Learner) -> None:
    attempt = learner.post("/v1/lessons/availability/attempts").json()["attempt"]["id"]
    body = discover(learner)
    assert body["primary_action"]["type"] == "continue_lesson"
    assert body["primary_action"]["attempt_id"] == attempt
    assert body["primary_action"]["lesson"]["slug"] == "availability"
    assert body["todays_lesson"]["slug"] == "anchoring"


def test_due_reviews_take_priority(learner: Learner, db_session: Session) -> None:
    complete_lesson(learner, db_session, "anchoring")
    learner.post("/v1/lessons/availability/attempts")
    learner.travel(days=1)
    body = discover(learner)
    assert body["primary_action"]["type"] == "review"
    assert body["primary_action"]["review"] == {
        "due_count": 1,
        "estimated_minutes": 1,
        "open_session_id": None,
    }
    assert body["reviews_due"] == 1

    session_id = learner.post("/v1/review-sessions").json()["session"]["id"]
    review = discover(learner)["primary_action"]["review"]
    assert review["open_session_id"] == session_id


def test_caught_up_when_everything_is_done(learner: Learner, db_session: Session) -> None:
    for slug in ("anchoring", "availability", "framing-effect"):
        complete_lesson(learner, db_session, slug)
    body = discover(learner)
    assert body["primary_action"] == {
        "type": "caught_up",
        "review": None,
        "lesson": None,
        "attempt_id": None,
        "next_review_on": "2026-11-03",
    }
    assert body["todays_lesson"] is None
    assert body["recommended"] == []
    assert body["progress"] == {"lessons_total": 3, "completed": 3, "understood": 0}
    assert body["xp"]["total"] == 3 * 25 + 10
    assert body["streak"]["done_today"] is True


def test_discover_matches_progress_and_review_summary(
    learner: Learner, db_session: Session
) -> None:
    complete_lesson(learner, db_session, "anchoring")
    learner.travel(days=1)
    body = discover(learner)
    progress = learner.get("/v1/progress").json()
    summary = learner.get("/v1/reviews/summary").json()
    assert body["reviews_due"] == summary["due_count"] == progress["reviews"]["due_count"]
    assert body["streak"] == progress["streak"]
    assert body["xp"] == progress["xp"]
    assert body["progress"]["completed"] == progress["lessons"]["completed"]


def test_completion_next_lesson_uses_interest_ranking(
    db_client: TestClient, clock: FixedClock, run_import: Importer, db_session: Session
) -> None:
    lessons = [
        make_lesson("lesson-a", topic="judgment", position=1, related=["lesson-b"]),
        make_lesson("lesson-b", topic="judgment", position=2, related=["lesson-a"]),
        make_lesson("lesson-c", topic="decisions", position=1, related=["lesson-a"]),
        make_lesson("lesson-d", topic="social", position=1, related=["lesson-a"]),
    ]
    run_import(lessons)
    learner = Learner(db_client, clock)
    set_interests(learner, ["social"])

    def finish(slug: str) -> Any:
        body = learner.post(f"/v1/lessons/{slug}/attempts").json()
        for q in body["content"]["questions"]:
            learner.post(
                f"/v1/attempts/{body['attempt']['id']}/answers",
                {"question_id": q["id"], "selected_option_ids": correct_ids(db_session, q["id"])},
            )
        return learner.post(f"/v1/attempts/{body['attempt']['id']}/complete").json()

    assert finish("lesson-a")["next_lesson"]["slug"] == "lesson-b"  # related first
    assert finish("lesson-b")["next_lesson"]["slug"] == "lesson-d"  # then interests
    assert finish("lesson-d")["next_lesson"]["slug"] == "lesson-c"
    assert finish("lesson-c")["next_lesson"] is None


def test_discover_requires_auth(db_client: TestClient) -> None:
    assert db_client.get("/v1/discover").status_code == 401
