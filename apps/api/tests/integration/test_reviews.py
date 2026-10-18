"""Due reviews, sessions, scheduling and history over simulated days (T-REC-*)."""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.content.models import AnswerOption, Question
from app.core.clock import FixedClock
from app.learning.models import UserLessonProgress
from app.reviews.models import ReviewEvent, ReviewSession, ReviewSessionItem, ReviewState
from tests.conftest import Importer
from tests.content_factory import make_lesson, standard_lessons

pytestmark = pytest.mark.db


class Learner:
    """A guest whose tokens are refreshed after the test clock jumps forward."""

    def __init__(self, client: TestClient, clock: FixedClock) -> None:
        self.client, self.clock = client, clock
        self.tokens = client.post("/v1/auth/guest", json={}).json()["tokens"]

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.tokens['access_token']}"}

    def travel(self, days: int = 0, **kwargs: int) -> None:
        """Advance the clock, refreshing at least every 29 days (refresh tokens last 30)."""
        remaining = timedelta(days=days, **kwargs)
        while True:
            step = min(remaining, timedelta(days=29))
            self.clock.advance(step)
            remaining -= step
            refreshed = self.client.post(
                "/v1/auth/refresh", json={"refresh_token": self.tokens["refresh_token"]}
            )
            assert refreshed.status_code == 200, refreshed.text
            self.tokens = refreshed.json()["tokens"]
            if remaining <= timedelta(0):
                break

    def get(self, path: str, **kwargs: Any) -> Any:
        return self.client.get(path, headers=self.headers, **kwargs)

    def post(self, path: str, json: Any = None) -> Any:
        return self.client.post(path, headers=self.headers, json=json)


@pytest.fixture
def learner(db_client: TestClient, clock: FixedClock, run_import: Importer) -> Learner:
    run_import(standard_lessons())
    return Learner(db_client, clock)


def correct_ids(db: Session, question_id: str) -> list[str]:
    return [
        str(i)
        for i in db.scalars(
            select(AnswerOption.id).where(
                AnswerOption.question_id == uuid.UUID(question_id), AnswerOption.is_correct
            )
        )
    ]


def wrong_ids(db: Session, question_id: str) -> list[str]:
    ids = db.scalars(
        select(AnswerOption.id).where(
            AnswerOption.question_id == uuid.UUID(question_id), AnswerOption.is_correct.is_(False)
        )
    )
    return [str(next(iter(ids)))]


def complete_lesson(learner: Learner, db: Session, slug: str = "anchoring") -> None:
    body = learner.post(f"/v1/lessons/{slug}/attempts").json()
    for q in body["content"]["questions"]:
        learner.post(
            f"/v1/attempts/{body['attempt']['id']}/answers",
            {"question_id": q["id"], "selected_option_ids": correct_ids(db, q["id"])},
        )
    assert learner.post(f"/v1/attempts/{body['attempt']['id']}/complete").status_code == 200


def review_once(learner: Learner, db: Session, *, correct: bool, guessed: bool = False) -> Any:
    session = learner.post("/v1/review-sessions").json()["session"]
    item = session["items"][0]
    ids = (
        correct_ids(db, item["question"]["id"])
        if correct
        else wrong_ids(db, item["question"]["id"])
    )
    response = learner.post(
        f"/v1/review-sessions/{session['id']}/items/{item['id']}/answer",
        {"selected_option_ids": ids, "guessed": guessed},
    )
    assert response.status_code == 201, response.text
    return response.json()


def card(learner: Learner, slug: str = "anchoring") -> dict[str, Any]:
    items = learner.get("/v1/lessons").json()["items"]
    progress: dict[str, Any] = next(i for i in items if i["slug"] == slug)["progress"]
    return progress


# --- due and summary --------------------------------------------------------------------------


def test_nothing_due_before_any_lesson(learner: Learner) -> None:
    assert learner.get("/v1/reviews/summary").json() == {
        "due_count": 0,
        "next_due_on": None,
        "in_review_count": 0,
        "open_session_id": None,
        "estimated_minutes": 0,
    }
    response = learner.post("/v1/review-sessions")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "NOTHING_DUE"
    assert response.json()["error"]["details"] == [{"next_due_on": None}]


def test_completed_lesson_becomes_due_the_next_local_day(
    learner: Learner, db_session: Session
) -> None:
    complete_lesson(learner, db_session)
    summary = learner.get("/v1/reviews/summary").json()
    assert summary["due_count"] == 0
    assert summary["next_due_on"] == "2026-11-03"
    assert summary["in_review_count"] == 1
    early = learner.post("/v1/review-sessions")
    assert early.json()["error"]["details"] == [{"next_due_on": "2026-11-03"}]

    learner.travel(days=1)
    summary = learner.get("/v1/reviews/summary").json()
    assert summary["due_count"] == 1
    assert summary["estimated_minutes"] == 1


def test_due_respects_the_users_timezone(learner: Learner, db_session: Session) -> None:
    learner.client.patch(
        "/v1/me/preferences", headers=learner.headers, json={"timezone": "Pacific/Auckland"}
    )
    complete_lesson(learner, db_session)  # 12:00Z = 01:00 on Nov 3 in Auckland -> due Nov 4
    learner.clock.set(datetime(2026, 11, 3, 10, 59, tzinfo=UTC))  # 23:59 Nov 3 local
    learner.travel()
    assert learner.get("/v1/reviews/summary").json()["due_count"] == 0
    learner.travel(minutes=1)  # 00:00 Nov 4 local
    assert learner.get("/v1/reviews/summary").json()["due_count"] == 1


def test_session_is_capped_and_matches_summary(
    db_client: TestClient, clock: FixedClock, run_import: Importer, db_session: Session
) -> None:
    lessons = [make_lesson(f"lesson-{i:02d}", position=i, related=["lesson-00"]) for i in range(22)]
    lessons[0]["related"] = ["lesson-01"]
    run_import(lessons)
    learner = Learner(db_client, clock)
    for lesson in reversed(lessons):  # completion order decides ties on due date
        complete_lesson(learner, db_session, lesson["slug"])
        learner.travel(minutes=1)
    learner.travel(days=1)
    summary = learner.get("/v1/reviews/summary").json()
    assert summary["due_count"] == 22
    assert summary["estimated_minutes"] == 10
    session = learner.post("/v1/review-sessions").json()["session"]
    assert session["item_count"] == 20
    expected = [lesson["slug"] for lesson in reversed(lessons)][:20]
    assert [i["lesson"]["slug"] for i in session["items"]] == expected


# --- sessions and answering ------------------------------------------------------------------


def test_session_is_reused_within_the_day(learner: Learner, db_session: Session) -> None:
    complete_lesson(learner, db_session)
    learner.travel(days=1)
    first = learner.post("/v1/review-sessions")
    assert first.status_code == 201
    session = first.json()["session"]
    assert session["status"] == "open"
    assert session["answered_count"] == 0
    again = learner.post("/v1/review-sessions")
    assert again.status_code == 200
    assert again.json()["resumed"] is True
    assert again.json()["session"]["id"] == session["id"]
    assert learner.get("/v1/reviews/summary").json()["open_session_id"] == session["id"]

    question = db_session.get(Question, uuid.UUID(session["items"][0]["question"]["id"]))
    assert question is not None
    assert question.role == "recall"  # never the lesson's own questions


def test_successful_review_reschedules_and_records_history(
    learner: Learner, db_session: Session
) -> None:
    complete_lesson(learner, db_session)
    learner.travel(days=1)
    body = review_once(learner, db_session, correct=True)
    result = body["result"]
    assert result["is_correct"] is True
    assert result["quality"] == 4
    assert result["schedule"] == {
        "previous_interval_days": 1,
        "next_interval_days": 6,
        "next_due_on": "2026-11-09",
    }
    assert result["mastery_stage"] == {"before": 1, "after": 2}
    assert body["session"] == {"answered_count": 1, "item_count": 1, "status": "completed"}
    assert body["session_summary"] == {
        "correct": 1,
        "total": 1,
        "advanced": [{"slug": "anchoring", "from": 1, "to": 2}],
        "to_revisit": [],
    }

    event = db_session.scalars(select(ReviewEvent)).one()
    assert (event.quality, event.interval_before, event.interval_after) == (4, 1, 6)
    assert event.review_number == 1
    assert event.days_since_last_review == 1
    progress = db_session.scalars(select(UserLessonProgress)).one()
    assert progress.first_recalled_at is not None
    assert progress.first_understood_at is None
    assert card(learner)["status"] == "recalled"
    assert learner.get("/v1/reviews/summary").json()["due_count"] == 0


def test_full_schedule_over_several_weeks(learner: Learner, db_session: Session) -> None:
    complete_lesson(learner, db_session)
    learner.travel(days=1)
    review_once(learner, db_session, correct=True)  # -> 6 days

    learner.travel(days=6)
    hard = review_once(learner, db_session, correct=True, guessed=True)["result"]
    assert hard["quality"] == 3
    assert hard["schedule"]["next_interval_days"] == 15
    assert hard["mastery_stage"] == {"before": 2, "after": 3}
    state = db_session.scalars(select(ReviewState)).one()
    assert state.ease_factor == Decimal("2.36")
    assert card(learner)["status"] == "understood"
    progress = db_session.scalars(select(UserLessonProgress)).one()
    understood_at = progress.first_understood_at
    assert understood_at is not None

    learner.travel(days=15)
    failed = review_once(learner, db_session, correct=False)
    assert failed["result"]["quality"] == 1
    assert failed["result"]["schedule"]["next_interval_days"] == 1
    assert failed["result"]["mastery_stage"] == {"before": 3, "after": 1}
    assert failed["session_summary"]["to_revisit"] == [
        {"slug": "anchoring", "title": "Lesson anchoring"}
    ]
    db_session.expire_all()
    state = db_session.scalars(select(ReviewState)).one()
    assert (state.repetitions, state.lapses, state.ease_factor) == (0, 1, Decimal("2.16"))
    assert card(learner)["status"] == "completed"  # current state drops...
    progress = db_session.scalars(select(UserLessonProgress)).one()
    assert progress.first_understood_at == understood_at  # ...milestones never do

    events = db_session.scalars(select(ReviewEvent).order_by(ReviewEvent.review_number)).all()
    assert [e.review_number for e in events] == [1, 2, 3]
    assert [e.days_since_last_review for e in events] == [1, 6, 15]


def test_consecutive_sessions_avoid_repeating_a_question(
    learner: Learner, db_session: Session
) -> None:
    complete_lesson(learner, db_session)
    previous = None
    for days in (1, 6, 15, 38):
        learner.travel(days=days)
        session = learner.post("/v1/review-sessions").json()["session"]
        question_id = session["items"][0]["question"]["id"]
        assert question_id != previous
        previous = question_id
        item = session["items"][0]
        learner.post(
            f"/v1/review-sessions/{session['id']}/items/{item['id']}/answer",
            {"selected_option_ids": correct_ids(db_session, question_id)},
        )


def test_answer_replay_and_validation(learner: Learner, db_session: Session) -> None:
    complete_lesson(learner, db_session)
    complete_lesson(learner, db_session, "availability")
    learner.travel(days=1)
    session = learner.post("/v1/review-sessions").json()["session"]
    item = session["items"][0]
    path = f"/v1/review-sessions/{session['id']}/items/{item['id']}/answer"
    options = [o["id"] for o in item["question"]["options"]]

    too_many = learner.post(path, {"selected_option_ids": options[:2]})
    assert too_many.json()["error"]["code"] == "INVALID_SELECTION_COUNT"
    foreign = learner.post(path, {"selected_option_ids": [str(uuid.uuid4())]})
    assert foreign.json()["error"]["code"] == "INVALID_OPTIONS"

    first = learner.post(
        path, {"selected_option_ids": wrong_ids(db_session, item["question"]["id"])}
    )
    assert first.status_code == 201
    replay = learner.post(
        path, {"selected_option_ids": correct_ids(db_session, item["question"]["id"])}
    )
    assert replay.status_code == 200
    assert replay.json()["replayed"] is True
    assert replay.json()["result"] == first.json()["result"]
    assert db_session.scalar(select(func.count()).select_from(ReviewEvent)) == 1

    unknown_item = learner.post(
        f"/v1/review-sessions/{session['id']}/items/{uuid.uuid4()}/answer",
        {"selected_option_ids": options[:1]},
    )
    assert unknown_item.json()["error"]["code"] == "ITEM_NOT_FOUND"


def test_ending_early_keeps_unanswered_items_due(learner: Learner, db_session: Session) -> None:
    complete_lesson(learner, db_session)
    complete_lesson(learner, db_session, "availability")
    learner.travel(days=1)
    session = learner.post("/v1/review-sessions").json()["session"]
    first, second = session["items"]
    learner.post(
        f"/v1/review-sessions/{session['id']}/items/{first['id']}/answer",
        {"selected_option_ids": correct_ids(db_session, first["question"]["id"])},
    )
    ended = learner.post(f"/v1/review-sessions/{session['id']}/end")
    assert ended.status_code == 200
    assert ended.json()["session"]["status"] == "ended_early"
    assert ended.json()["summary"]["total"] == 1
    assert learner.post(f"/v1/review-sessions/{session['id']}/end").status_code == 200

    late = learner.post(
        f"/v1/review-sessions/{session['id']}/items/{second['id']}/answer",
        {"selected_option_ids": correct_ids(db_session, second["question"]["id"])},
    )
    assert late.status_code == 409
    assert late.json()["error"]["code"] == "SESSION_NOT_OPEN"
    assert learner.get("/v1/reviews/summary").json()["due_count"] == 1
    fresh = learner.post("/v1/review-sessions").json()["session"]
    assert [i["lesson"]["slug"] for i in fresh["items"]] == [second["lesson"]["slug"]]


def test_yesterdays_open_session_expires(learner: Learner, db_session: Session) -> None:
    complete_lesson(learner, db_session)
    learner.travel(days=1)
    old = learner.post("/v1/review-sessions").json()["session"]["id"]
    learner.travel(days=1)
    new = learner.post("/v1/review-sessions")
    assert new.status_code == 201
    assert new.json()["session"]["id"] != old
    expired = db_session.get(ReviewSession, uuid.UUID(old))
    assert expired is not None
    assert expired.status == "expired"
    assert learner.get(f"/v1/review-sessions/{old}").json()["session"]["status"] == "expired"


def test_retired_lessons_stay_reviewable(
    learner: Learner, db_session: Session, run_import: Importer
) -> None:
    complete_lesson(learner, db_session, "availability")
    lessons = standard_lessons()
    lessons[1]["status"] = "retired"
    run_import(lessons)
    learner.travel(days=1)
    session = learner.post("/v1/review-sessions").json()["session"]
    assert session["items"][0]["lesson"]["slug"] == "availability"


# --- concepts list -------------------------------------------------------------------------------


def test_concepts_list_and_pagination(learner: Learner, db_session: Session) -> None:
    complete_lesson(learner, db_session, "anchoring")
    learner.travel(days=1)
    complete_lesson(learner, db_session, "framing-effect")
    review_once(learner, db_session, correct=True)  # anchoring -> due Nov 9

    page = learner.get("/v1/reviews/concepts").json()
    assert page["items"] == [
        {
            "lesson": {"slug": "framing-effect", "title": "Lesson framing-effect"},
            "mastery_stage": 1,
            "due_on": "2026-11-04",
            "is_due": False,
        },
        {
            "lesson": {"slug": "anchoring", "title": "Lesson anchoring"},
            "mastery_stage": 2,
            "due_on": "2026-11-09",
            "is_due": False,
        },
    ]
    first = learner.get("/v1/reviews/concepts", params={"limit": 1}).json()
    second = learner.get(
        "/v1/reviews/concepts", params={"limit": 1, "cursor": first["next_cursor"]}
    ).json()
    assert [first["items"][0]["lesson"]["slug"], second["items"][0]["lesson"]["slug"]] == [
        "framing-effect",
        "anchoring",
    ]
    assert second["next_cursor"] is None
    bad = learner.get("/v1/reviews/concepts", params={"cursor": "bm9wZQ"})
    assert bad.status_code == 422


# --- isolation and deletion --------------------------------------------------------------------


def test_sessions_are_private(learner: Learner, db_session: Session) -> None:
    complete_lesson(learner, db_session)
    learner.travel(days=1)
    session = learner.post("/v1/review-sessions").json()["session"]
    item = session["items"][0]
    other = Learner(learner.client, learner.clock)
    assert other.get(f"/v1/review-sessions/{session['id']}").status_code == 404
    response = other.post(
        f"/v1/review-sessions/{session['id']}/items/{item['id']}/answer",
        {"selected_option_ids": correct_ids(db_session, item["question"]["id"])},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SESSION_NOT_FOUND"
    assert other.post(f"/v1/review-sessions/{session['id']}/end").status_code == 404
    assert other.get("/v1/reviews/summary").json()["due_count"] == 0


def test_account_deletion_removes_review_data(learner: Learner, db_session: Session) -> None:
    complete_lesson(learner, db_session)
    learner.travel(days=1)
    review_once(learner, db_session, correct=True)
    learner.client.request("DELETE", "/v1/me", headers=learner.headers, json={"confirm": "DELETE"})
    db_session.expire_all()
    for model in (ReviewState, ReviewSession, ReviewSessionItem, ReviewEvent):
        assert db_session.scalar(select(func.count()).select_from(model)) == 0
