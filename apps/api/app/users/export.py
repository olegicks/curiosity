"""Personal data export (docs/spec/05 §5.3, 09 §9.6). Read-only, owner-scoped."""

import uuid
from collections.abc import Iterable
from datetime import datetime
from typing import Any

from fastapi.encoders import jsonable_encoder
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from app.ai.models import AiExplanationFeedback
from app.analytics.models import ProductEvent
from app.auth.models import User
from app.core.db import Base
from app.gamification.models import DailyActivity, StreakState, UserAchievement, XpTransaction
from app.learning.models import (
    ContentFeedback,
    LessonAttempt,
    LessonAttemptAnswer,
    LessonRating,
    UserLessonProgress,
)
from app.reviews.models import ReviewEvent, ReviewSession, ReviewSessionItem, ReviewState
from app.users.models import UserPreferences
from app.users.service import interest_topic_slugs

EXPORT_FORMAT_VERSION = 1
NEVER_EXPORTED = {"password_hash", "token_version"}


def _row(obj: Base, *, exclude: Iterable[str] = ()) -> dict[str, Any]:
    skip = NEVER_EXPORTED | set(exclude)
    return {
        attr.key: getattr(obj, attr.key)
        for attr in inspect(obj).mapper.column_attrs
        if attr.key not in skip
    }


def _rows(db: Session, model: type[Base], *where: Any) -> list[dict[str, Any]]:
    return [_row(obj) for obj in db.scalars(select(model).where(*where))]


def build_export(db: Session, user: User, now: datetime) -> dict[str, Any]:
    uid: uuid.UUID = user.id
    attempts = list(
        db.scalars(
            select(LessonAttempt)
            .where(LessonAttempt.user_id == uid)
            .order_by(LessonAttempt.started_at)
        )
    )
    answers: dict[uuid.UUID, list[dict[str, Any]]] = {a.id: [] for a in attempts}
    for answer in db.scalars(
        select(LessonAttemptAnswer).where(LessonAttemptAnswer.attempt_id.in_(list(answers)))
    ):
        answers[answer.attempt_id].append(_row(answer))

    sessions = list(db.scalars(select(ReviewSession).where(ReviewSession.user_id == uid)))
    items: dict[uuid.UUID, list[dict[str, Any]]] = {s.id: [] for s in sessions}
    for item in db.scalars(
        select(ReviewSessionItem).where(ReviewSessionItem.session_id.in_(list(items)))
    ):
        items[item.session_id].append(_row(item))

    preferences = db.get(UserPreferences, uid)
    streak = db.get(StreakState, uid)
    data = {
        "format_version": EXPORT_FORMAT_VERSION,
        "exported_at": now,
        "user": _row(user),
        "preferences": _row(preferences) if preferences else None,
        "interest_topics": interest_topic_slugs(db, uid),
        "lesson_attempts": [{**_row(a), "answers": answers[a.id]} for a in attempts],
        "lesson_progress": _rows(db, UserLessonProgress, UserLessonProgress.user_id == uid),
        "lesson_ratings": _rows(db, LessonRating, LessonRating.user_id == uid),
        "content_feedback": _rows(db, ContentFeedback, ContentFeedback.user_id == uid),
        "review_states": _rows(db, ReviewState, ReviewState.user_id == uid),
        "review_sessions": [{**_row(s), "items": items[s.id]} for s in sessions],
        "review_events": _rows(db, ReviewEvent, ReviewEvent.user_id == uid),
        "xp_transactions": _rows(db, XpTransaction, XpTransaction.user_id == uid),
        "streak": _row(streak) if streak else None,
        "daily_activity": _rows(db, DailyActivity, DailyActivity.user_id == uid),
        "achievements": _rows(db, UserAchievement, UserAchievement.user_id == uid),
        "ai_explanation_feedback": _rows(
            db, AiExplanationFeedback, AiExplanationFeedback.user_id == uid
        ),
        "product_events": _rows(db, ProductEvent, ProductEvent.user_id == uid),
    }
    encoded: dict[str, Any] = jsonable_encoder(data)
    return encoded
