"""XP, daily activity, streaks and achievements (docs/spec/07 §7.4-7.7).

These functions run *inside* the caller's transaction (lesson completion, review
answers) and never commit. Duplicate awards are impossible: every XP row and
achievement is inserted with ON CONFLICT DO NOTHING on its natural key. Lock
order follows spec 04 §4.9: the caller's rows -> streak -> daily activity.
"""

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.content.models import Lesson
from app.core.ids import uuid7
from app.gamification import rules
from app.gamification.models import DailyActivity, StreakState, UserAchievement, XpTransaction
from app.gamification.rules import ACHIEVEMENTS, ACHIEVEMENTS_BY_CODE, Trigger, XpReason
from app.gamification.schemas import AchievementOut, StreakOut, XpAwardOut, XpSummaryOut
from app.gamification.streaks import Streak, record_streak_day, view_streak
from app.learning.models import UserLessonProgress
from app.reviews.models import ReviewSession
from app.users.service import get_preferences


@dataclass
class Rewards:
    xp_awarded: list[XpAwardOut] = field(default_factory=list)
    achievements_unlocked: list[AchievementOut] = field(default_factory=list)

    @property
    def daily_goal_reached_now(self) -> bool:
        return any(a.reason == XpReason.DAILY_GOAL for a in self.xp_awarded)


# --- building blocks ------------------------------------------------------------------------


def _bump_activity(db: Session, user_id: uuid.UUID, day: date, **counts: int) -> None:
    insert = pg_insert(DailyActivity).values(user_id=user_id, local_date=day, **counts)
    db.execute(
        insert.on_conflict_do_update(
            index_elements=["user_id", "local_date"],
            set_={
                name: getattr(DailyActivity, name) + getattr(insert.excluded, name)
                for name in counts
            }
            | {"updated_at": func.now()},
        )
    )


def _award(
    db: Session,
    user_id: uuid.UUID,
    reason: XpReason,
    amount: int,
    key: str,
    day: date,
    refs: dict[str, Any],
) -> XpAwardOut | None:
    inserted = db.execute(
        pg_insert(XpTransaction)
        .values(
            id=uuid7(),
            user_id=user_id,
            amount=amount,
            reason=reason.value,
            idempotency_key=key,
            local_date=day,
            **refs,
        )
        .on_conflict_do_nothing(index_elements=["user_id", "idempotency_key"])
        .returning(XpTransaction.id)
    ).scalar_one_or_none()
    if inserted is None:
        return None
    _bump_activity(db, user_id, day, xp_earned=amount)
    return XpAwardOut(reason=reason.value, amount=amount)


def _today_xp(db: Session, user_id: uuid.UUID, day: date, *, include_bonus: bool = True) -> int:
    stmt = select(func.coalesce(func.sum(XpTransaction.amount), 0)).where(
        XpTransaction.user_id == user_id, XpTransaction.local_date == day
    )
    if not include_bonus:
        stmt = stmt.where(XpTransaction.reason != XpReason.DAILY_GOAL.value)
    return int(db.scalar(stmt) or 0)


def _maybe_daily_goal(
    db: Session, user_id: uuid.UUID, day: date, refs: dict[str, Any]
) -> XpAwardOut | None:
    goal = get_preferences(db, user_id).daily_xp_goal
    if _today_xp(db, user_id, day, include_bonus=False) < goal:
        return None
    return _award(
        db,
        user_id,
        XpReason.DAILY_GOAL,
        rules.XP_DAILY_GOAL,
        rules.daily_goal_key(day.isoformat()),
        day,
        refs,
    )


def _locked_streak(db: Session, user_id: uuid.UUID) -> StreakState:
    db.execute(pg_insert(StreakState).values(user_id=user_id).on_conflict_do_nothing())
    state = db.scalar(select(StreakState).where(StreakState.user_id == user_id).with_for_update())
    assert state is not None  # noqa: S101 - inserted above
    return state


def _as_streak(state: StreakState | None) -> Streak:
    if state is None:
        return Streak()
    return Streak(
        current=state.current_streak,
        longest=state.longest_streak,
        last_date=state.last_streak_date,
        freezes_available=state.freezes_available,
        freezes_used_total=state.freezes_used_total,
    )


def _record_streak(db: Session, user_id: uuid.UUID, day: date) -> Streak:
    state = _locked_streak(db, user_id)
    updated = record_streak_day(_as_streak(state), day)
    state.current_streak = updated.current
    state.longest_streak = updated.longest
    state.last_streak_date = updated.last_date
    state.freezes_available = updated.freezes_available
    state.freezes_used_total = updated.freezes_used_total
    return updated


# --- achievements -----------------------------------------------------------------------------


def _achievement_out(code: str, earned_at: datetime | None) -> AchievementOut:
    definition = ACHIEVEMENTS_BY_CODE[code]
    return AchievementOut(
        code=code, title=definition.title, description=definition.description, earned_at=earned_at
    )


def _count_progress(db: Session, user_id: uuid.UUID, column: Any) -> int:
    return int(
        db.scalar(
            select(func.count())
            .select_from(UserLessonProgress)
            .where(UserLessonProgress.user_id == user_id, column.is_not(None))
        )
        or 0
    )


def _topic_completed(db: Session, user_id: uuid.UUID, lesson_id: uuid.UUID) -> bool:
    topic_id = db.scalar(select(Lesson.topic_id).where(Lesson.id == lesson_id))
    published = select(Lesson.id).where(Lesson.topic_id == topic_id, Lesson.status == "published")
    total = db.scalar(select(func.count()).select_from(published.subquery())) or 0
    done = db.scalar(
        select(func.count())
        .select_from(UserLessonProgress)
        .where(
            UserLessonProgress.user_id == user_id,
            UserLessonProgress.first_completed_at.is_not(None),
            UserLessonProgress.lesson_id.in_(published),
        )
    )
    return total > 0 and done == total


def _achievement_value(
    db: Session, user_id: uuid.UUID, code: str, lesson_id: uuid.UUID | None, streak: int
) -> int:
    match code:
        case "first_lesson" | "five_lessons":
            return _count_progress(db, user_id, UserLessonProgress.first_completed_at)
        case "topic_complete":
            return int(lesson_id is not None and _topic_completed(db, user_id, lesson_id))
        case "first_recall":
            return _count_progress(db, user_id, UserLessonProgress.first_recalled_at)
        case "first_understood" | "ten_understood":
            return _count_progress(db, user_id, UserLessonProgress.first_understood_at)
        case "streak_7":
            return streak
        case "reviews_10":
            return int(
                db.scalar(
                    select(func.count())
                    .select_from(ReviewSession)
                    .where(ReviewSession.user_id == user_id, ReviewSession.status == "completed")
                )
                or 0
            )
    raise ValueError(f"unknown achievement {code}")


def _evaluate(
    db: Session,
    user_id: uuid.UUID,
    triggers: set[Trigger],
    *,
    source_key: str,
    now: datetime,
    lesson_id: uuid.UUID | None = None,
    streak: int = 0,
) -> list[AchievementOut]:
    earned = set(db.scalars(select(UserAchievement.code).where(UserAchievement.user_id == user_id)))
    unlocked = []
    for definition in ACHIEVEMENTS:
        if definition.trigger not in triggers or definition.code in earned:
            continue
        value = _achievement_value(db, user_id, definition.code, lesson_id, streak)
        if value < definition.threshold:
            continue
        inserted = db.execute(
            pg_insert(UserAchievement)
            .values(user_id=user_id, code=definition.code, earned_at=now, source_key=source_key)
            .on_conflict_do_nothing()
            .returning(UserAchievement.code)
        ).scalar_one_or_none()
        if inserted is not None:
            unlocked.append(_achievement_out(definition.code, now))
    return unlocked


# --- events ------------------------------------------------------------------------------------


def on_lesson_question_answered(db: Session, user_id: uuid.UUID, day: date) -> None:
    _bump_activity(db, user_id, day, lesson_questions_answered=1)


def on_lesson_completed(
    db: Session,
    user_id: uuid.UUID,
    *,
    attempt_id: uuid.UUID,
    lesson_id: uuid.UUID,
    first_completion: bool,
    perfect: bool,
    day: date,
    now: datetime,
) -> Rewards:
    """Any completion counts as a streak day; XP only for the first completion."""
    streak = _record_streak(db, user_id, day)
    _bump_activity(db, user_id, day, lessons_completed=1)
    refs = {"lesson_id": lesson_id, "attempt_id": attempt_id}
    rewards = Rewards()
    if first_completion:
        awards = [
            _award(
                db,
                user_id,
                XpReason.LESSON_COMPLETE,
                rules.XP_LESSON_COMPLETE,
                rules.lesson_complete_key(lesson_id),
                day,
                refs,
            )
        ]
        if perfect:
            awards.append(
                _award(
                    db,
                    user_id,
                    XpReason.LESSON_PERFECT,
                    rules.XP_LESSON_PERFECT,
                    rules.lesson_perfect_key(lesson_id),
                    day,
                    refs,
                )
            )
        awards.append(_maybe_daily_goal(db, user_id, day, {"attempt_id": attempt_id}))
        rewards.xp_awarded = [a for a in awards if a is not None]
    rewards.achievements_unlocked = _evaluate(
        db,
        user_id,
        {Trigger.LESSON_COMPLETED, Trigger.STREAK_UPDATED},
        source_key=f"attempt:{attempt_id}",
        now=now,
        lesson_id=lesson_id,
        streak=streak.current,
    )
    return rewards


def on_review_answered(
    db: Session,
    user_id: uuid.UUID,
    *,
    session_id: uuid.UUID,
    item_id: uuid.UUID,
    lesson_id: uuid.UUID,
    correct: bool,
    session_completed: bool,
    day: date,
    now: datetime,
) -> Rewards:
    triggers = {Trigger.REVIEW_ANSWERED}
    streak = 0
    if session_completed:  # completing a review session is a streak day
        streak = _record_streak(db, user_id, day).current
        triggers |= {Trigger.SESSION_COMPLETED, Trigger.STREAK_UPDATED}
        _bump_activity(db, user_id, day, review_sessions_completed=1)
    _bump_activity(db, user_id, day, review_items_answered=1)

    refs = {"review_session_id": session_id, "review_session_item_id": item_id}
    awards = [
        _award(
            db,
            user_id,
            XpReason.REVIEW_ITEM,
            rules.XP_REVIEW_CORRECT if correct else rules.XP_REVIEW_INCORRECT,
            rules.review_item_key(item_id),
            day,
            {**refs, "lesson_id": lesson_id},
        )
    ]
    if session_completed:
        awards.append(
            _award(
                db,
                user_id,
                XpReason.REVIEW_SESSION,
                rules.XP_REVIEW_SESSION,
                rules.review_session_key(session_id),
                day,
                refs,
            )
        )
    awards.append(_maybe_daily_goal(db, user_id, day, refs))
    return Rewards(
        xp_awarded=[a for a in awards if a is not None],
        achievements_unlocked=_evaluate(
            db, user_id, triggers, source_key=f"review_item:{item_id}", now=now, streak=streak
        ),
    )


# --- replays and read models ------------------------------------------------------------------


def _replay(db: Session, user_id: uuid.UUID, xp_filter: Any, source_key: str) -> Rewards:
    rows = db.scalars(
        select(XpTransaction)
        .where(XpTransaction.user_id == user_id, xp_filter)
        .order_by(XpTransaction.created_at, XpTransaction.id)
    )
    achievements = db.scalars(
        select(UserAchievement).where(
            UserAchievement.user_id == user_id, UserAchievement.source_key == source_key
        )
    )
    return Rewards(
        xp_awarded=[XpAwardOut(reason=r.reason, amount=r.amount) for r in rows],
        achievements_unlocked=[_achievement_out(a.code, a.earned_at) for a in achievements],
    )


def rewards_for_attempt(db: Session, user_id: uuid.UUID, attempt_id: uuid.UUID) -> Rewards:
    return _replay(db, user_id, XpTransaction.attempt_id == attempt_id, f"attempt:{attempt_id}")


def rewards_for_review_item(db: Session, user_id: uuid.UUID, item_id: uuid.UUID) -> Rewards:
    return _replay(
        db, user_id, XpTransaction.review_session_item_id == item_id, f"review_item:{item_id}"
    )


def session_xp_total(db: Session, user_id: uuid.UUID, session_id: uuid.UUID) -> int:
    return int(
        db.scalar(
            select(func.coalesce(func.sum(XpTransaction.amount), 0)).where(
                XpTransaction.user_id == user_id, XpTransaction.review_session_id == session_id
            )
        )
        or 0
    )


def total_xp(db: Session, user_id: uuid.UUID) -> int:
    return int(
        db.scalar(
            select(func.coalesce(func.sum(XpTransaction.amount), 0)).where(
                XpTransaction.user_id == user_id
            )
        )
        or 0
    )


def xp_summary(
    db: Session, user_id: uuid.UUID, day: date, *, reached_now: bool = False
) -> XpSummaryOut:
    return XpSummaryOut(
        today=_today_xp(db, user_id, day),
        goal=get_preferences(db, user_id).daily_xp_goal,
        total=total_xp(db, user_id),
        daily_goal_reached_now=reached_now,
    )


def streak_out(db: Session, user_id: uuid.UUID, today: date) -> StreakOut:
    state = db.get(StreakState, user_id)
    view = view_streak(_as_streak(state), today)
    return StreakOut(
        current=view.current,
        longest=view.longest,
        freezes_available=view.freezes_available,
        done_today=view.done_today,
        at_risk=view.at_risk,
    )


def achievements(db: Session, user_id: uuid.UUID) -> list[AchievementOut]:
    earned = {
        a.code: a.earned_at
        for a in db.scalars(select(UserAchievement).where(UserAchievement.user_id == user_id))
    }
    return [_achievement_out(d.code, earned.get(d.code)) for d in ACHIEVEMENTS]
