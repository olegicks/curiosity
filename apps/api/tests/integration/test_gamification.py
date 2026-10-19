"""XP, daily goal, streaks, achievements, /progress and /achievements (T-GAM-*)."""

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.clock import FixedClock
from app.gamification.models import DailyActivity, StreakState, UserAchievement, XpTransaction
from tests.conftest import Importer
from tests.content_factory import standard_lessons
from tests.helpers import Learner, complete_lesson, correct_ids, review_once, wrong_ids

pytestmark = pytest.mark.db


@pytest.fixture
def learner(db_client: TestClient, clock: FixedClock, run_import: Importer) -> Learner:
    run_import(standard_lessons())
    return Learner(db_client, clock)


def set_goal(learner: Learner, goal: int) -> None:
    response = learner.client.patch(
        "/v1/me/preferences", headers=learner.headers, json={"daily_xp_goal": goal}
    )
    assert response.status_code == 200


def finish(learner: Learner, db: Session, slug: str = "anchoring", *, perfect: bool = True) -> Any:
    """Complete a lesson and return the completion response body."""
    body = learner.post(f"/v1/lessons/{slug}/attempts").json()
    for i, q in enumerate(body["content"]["questions"]):
        ids = correct_ids(db, q["id"]) if perfect or i else wrong_ids(db, q["id"])
        learner.post(
            f"/v1/attempts/{body['attempt']['id']}/answers",
            {"question_id": q["id"], "selected_option_ids": ids},
        )
    response = learner.post(f"/v1/attempts/{body['attempt']['id']}/complete")
    assert response.status_code == 200, response.text
    result: dict[str, Any] = response.json()
    return result


def xp_total(db: Session) -> int:
    return int(db.scalar(select(func.coalesce(func.sum(XpTransaction.amount), 0))) or 0)


def awards(body: dict[str, Any]) -> list[tuple[str, int]]:
    return [(a["reason"], a["amount"]) for a in body["xp_awarded"]]


# --- lesson completion -----------------------------------------------------------------------


def test_first_completion_awards_xp_streak_and_achievement(
    learner: Learner, db_session: Session
) -> None:
    body = finish(learner, db_session)
    assert awards(body) == [("lesson_complete", 20), ("lesson_perfect", 5), ("daily_goal", 10)]
    assert body["xp"] == {"today": 35, "goal": 20, "total": 35, "daily_goal_reached_now": True}
    assert body["streak"] == {
        "current": 1,
        "longest": 1,
        "freezes_available": 1,
        "done_today": True,
        "at_risk": False,
    }
    assert [a["code"] for a in body["achievements_unlocked"]] == ["first_lesson"]


def test_completion_replay_returns_same_rewards_without_new_rows(
    learner: Learner, db_session: Session
) -> None:
    body = learner.post("/v1/lessons/anchoring/attempts").json()
    attempt = body["attempt"]["id"]
    for q in body["content"]["questions"]:
        learner.post(
            f"/v1/attempts/{attempt}/answers",
            {"question_id": q["id"], "selected_option_ids": correct_ids(db_session, q["id"])},
        )
    first = learner.post(f"/v1/attempts/{attempt}/complete").json()
    for _ in range(3):
        replay = learner.post(f"/v1/attempts/{attempt}/complete").json()
        assert replay["replayed"] is True
        assert replay["xp_awarded"] == first["xp_awarded"]
        assert replay["achievements_unlocked"] == first["achievements_unlocked"]
    assert xp_total(db_session) == 35
    assert db_session.scalar(select(func.count()).select_from(XpTransaction)) == 3


def test_imperfect_first_completion_has_no_bonus(learner: Learner, db_session: Session) -> None:
    set_goal(learner, 40)
    body = finish(learner, db_session, perfect=False)
    assert awards(body) == [("lesson_complete", 20)]
    assert body["xp"]["daily_goal_reached_now"] is False


def test_revisit_counts_for_streak_but_earns_no_xp(learner: Learner, db_session: Session) -> None:
    finish(learner, db_session)
    learner.travel(days=1)
    revisit = finish(learner, db_session)
    assert revisit["xp_awarded"] == []
    assert revisit["streak"]["current"] == 2
    assert xp_total(db_session) == 35
    activity = db_session.scalars(select(DailyActivity).order_by(DailyActivity.local_date)).all()
    assert [a.lessons_completed for a in activity] == [1, 1]
    assert [a.xp_earned for a in activity] == [35, 0]


def test_daily_goal_bonus_once_per_day(learner: Learner, db_session: Session) -> None:
    first = finish(learner, db_session, "anchoring")
    second = finish(learner, db_session, "availability")
    assert ("daily_goal", 10) in awards(first)
    assert awards(second) == [("lesson_complete", 20), ("lesson_perfect", 5)]
    assert second["xp"]["daily_goal_reached_now"] is False
    learner.travel(days=1)
    third = finish(learner, db_session, "framing-effect")
    assert ("daily_goal", 10) in awards(third)


def test_lowering_the_goal_applies_on_the_next_xp_event(
    learner: Learner, db_session: Session
) -> None:
    set_goal(learner, 60)
    assert ("daily_goal", 10) not in awards(finish(learner, db_session, "anchoring"))
    set_goal(learner, 20)
    later = finish(learner, db_session, "availability")
    assert ("daily_goal", 10) in awards(later)


# --- reviews ----------------------------------------------------------------------------------


def test_review_answers_award_xp_and_complete_streak_day(
    learner: Learner, db_session: Session
) -> None:
    set_goal(learner, 60)
    complete_lesson(learner, db_session, "anchoring")
    complete_lesson(learner, db_session, "availability")
    learner.travel(days=1)
    session = learner.post("/v1/review-sessions").json()["session"]
    first, second = session["items"]

    wrong = learner.post(
        f"/v1/review-sessions/{session['id']}/items/{first['id']}/answer",
        {"selected_option_ids": wrong_ids(db_session, first["question"]["id"])},
    ).json()
    assert awards(wrong) == [("review_item", 1)]
    assert wrong["streak"] is None  # session not finished yet

    right = learner.post(
        f"/v1/review-sessions/{session['id']}/items/{second['id']}/answer",
        {"selected_option_ids": correct_ids(db_session, second["question"]["id"])},
    ).json()
    assert awards(right) == [("review_item", 5), ("review_session", 10)]
    assert right["streak"]["current"] == 2
    assert right["session_summary"]["xp_total"] == 16
    assert [a["code"] for a in right["achievements_unlocked"]] == ["first_recall"]

    replay = learner.post(
        f"/v1/review-sessions/{session['id']}/items/{second['id']}/answer",
        {"selected_option_ids": correct_ids(db_session, second["question"]["id"])},
    ).json()
    assert replay["replayed"] is True
    assert replay["xp_awarded"] == right["xp_awarded"]
    assert replay["achievements_unlocked"] == right["achievements_unlocked"]

    day = db_session.scalars(
        select(DailyActivity).order_by(DailyActivity.local_date.desc())
    ).first()
    assert day is not None
    assert (day.review_items_answered, day.review_sessions_completed, day.xp_earned) == (2, 1, 16)


def test_daily_activity_matches_the_xp_ledger(learner: Learner, db_session: Session) -> None:
    finish(learner, db_session, "anchoring")
    learner.travel(days=1)
    review_once(learner, db_session, correct=True)
    finish(learner, db_session, "availability")
    for activity in db_session.scalars(select(DailyActivity)):
        ledger = db_session.scalar(
            select(func.coalesce(func.sum(XpTransaction.amount), 0)).where(
                XpTransaction.local_date == activity.local_date
            )
        )
        assert activity.xp_earned == ledger
    first_day = db_session.scalars(select(DailyActivity).order_by(DailyActivity.local_date)).first()
    assert first_day is not None
    assert first_day.lesson_questions_answered == 2


# --- streaks ---------------------------------------------------------------------------------


def test_freeze_covers_a_missed_day_and_seven_days_unlock_streak_7(
    learner: Learner, db_session: Session
) -> None:
    finish(learner, db_session)
    learner.travel(days=2)  # skip a day: the starting freeze covers it
    body = finish(learner, db_session)
    assert body["streak"]["current"] == 2
    assert body["streak"]["freezes_available"] == 0
    for _ in range(5):
        learner.travel(days=1)
        body = finish(learner, db_session)
    assert body["streak"]["current"] == 7
    assert body["streak"]["freezes_available"] == 1  # earned at day 7
    assert [a["code"] for a in body["achievements_unlocked"]] == ["streak_7"]


def test_progress_reports_a_broken_streak_as_zero(learner: Learner, db_session: Session) -> None:
    finish(learner, db_session)
    learner.travel(days=1)
    streak = learner.get("/v1/progress").json()["streak"]
    assert (streak["current"], streak["done_today"], streak["at_risk"]) == (1, False, False)
    learner.travel(days=1)  # yesterday missed; the freeze would cover it if they learn today
    assert learner.get("/v1/progress").json()["streak"]["at_risk"] is True
    learner.travel(days=1)
    assert learner.get("/v1/progress").json()["streak"]["current"] == 0
    stored = db_session.scalars(select(StreakState)).one()
    assert stored.current_streak == 1  # display decays lazily; storage resets on next activity


# --- achievements ---------------------------------------------------------------------------


def test_topic_and_five_lesson_achievements(
    db_client: TestClient, clock: FixedClock, run_import: Importer, db_session: Session
) -> None:
    lessons = standard_lessons()
    for i, slug in enumerate(["extra-a", "extra-b"], start=10):
        extra = dict(lessons[2], slug=slug, position=i, id=str(uuid.uuid4()))
        lessons.append(extra)
    run_import(lessons)
    learner = Learner(db_client, clock)
    unlocked: list[str] = []
    for slug in ["anchoring", "availability", "framing-effect", "extra-a", "extra-b"]:
        unlocked += [a["code"] for a in finish(learner, db_session, slug)["achievements_unlocked"]]
    assert unlocked == ["first_lesson", "topic_complete", "five_lessons"]

    items = learner.get("/v1/achievements").json()["items"]
    assert len(items) == 8
    earned = {i["code"] for i in items if i["earned_at"] is not None}
    assert earned == {"first_lesson", "topic_complete", "five_lessons"}
    assert db_session.scalar(select(func.count()).select_from(UserAchievement)) == 3


# --- /progress -------------------------------------------------------------------------------


def test_progress_overview(learner: Learner, db_session: Session) -> None:
    empty = learner.get("/v1/progress").json()
    assert empty["lessons"] == {
        "total": 3,
        "started": 0,
        "completed": 0,
        "by_stage": {"1": 0, "2": 0, "3": 0, "4": 0},
    }
    assert empty["recall_accuracy"] == {"correct": 0, "total": 0}

    finish(learner, db_session, "anchoring")
    learner.post("/v1/lessons/availability/attempts")
    learner.travel(days=1)
    review_once(learner, db_session, correct=True)

    body = learner.get("/v1/progress").json()
    assert body["lessons"] == {
        "total": 3,
        "started": 2,
        "completed": 1,
        "by_stage": {"1": 0, "2": 1, "3": 0, "4": 0},
    }
    assert body["by_topic"] == [
        {"slug": "judgment", "title": "Judgment", "total": 2, "completed": 1},
        {"slug": "decisions", "title": "Decisions", "total": 1, "completed": 0},
    ]
    assert body["xp"] == {"total": 50, "today": 15, "goal": 20}
    assert body["recall_accuracy"] == {"correct": 1, "total": 1}
    assert body["reviews"] == {"due_count": 0, "next_due_on": "2026-11-09"}
    assert body["streak"]["current"] == 2


def test_account_deletion_removes_gamification_rows(learner: Learner, db_session: Session) -> None:
    finish(learner, db_session)
    learner.client.request("DELETE", "/v1/me", headers=learner.headers, json={"confirm": "DELETE"})
    db_session.expire_all()
    for model in (XpTransaction, StreakState, DailyActivity, UserAchievement):
        assert db_session.scalar(select(func.count()).select_from(model)) == 0
