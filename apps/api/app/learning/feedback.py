"""Lesson ratings and "report a problem" (docs/spec/05 §5.5)."""

import uuid
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.content import service as content
from app.content.models import Lesson, LessonVersion, Question
from app.core.errors import ConflictError, RateLimitedError, ValidationError
from app.learning.models import ContentFeedback, LessonRating
from app.learning.schemas import ContentFeedbackIn
from app.learning.service import get_owned_attempt

FEEDBACK_PER_DAY = 10


class AttemptNotCompletedError(ConflictError):
    code = "ATTEMPT_NOT_COMPLETED"
    message = "Rate the lesson after completing it."


class InvalidReferenceError(ValidationError):
    code = "INVALID_REFERENCE"
    message = "The referenced lesson version or question does not match this lesson."


def rate_attempt(
    db: Session, user_id: uuid.UUID, attempt_id: uuid.UUID, rating: str, now: datetime
) -> None:
    """Upsert one rating per user and lesson version."""
    attempt = get_owned_attempt(db, user_id, attempt_id)
    if attempt.status != "completed":
        raise AttemptNotCompletedError
    db.execute(
        pg_insert(LessonRating)
        .values(user_id=user_id, lesson_version_id=attempt.lesson_version_id, rating=rating)
        .on_conflict_do_update(
            index_elements=["user_id", "lesson_version_id"],
            set_={"rating": rating, "updated_at": now},
        )
    )
    db.commit()


def submit_feedback(
    db: Session, user_id: uuid.UUID, slug: str, body: ContentFeedbackIn, now: datetime
) -> uuid.UUID:
    lesson = content.get_published_lesson(db, slug)
    recent = db.scalar(
        select(func.count())
        .select_from(ContentFeedback)
        .where(
            ContentFeedback.user_id == user_id, ContentFeedback.created_at > now - timedelta(days=1)
        )
    )
    if (recent or 0) >= FEEDBACK_PER_DAY:
        raise RateLimitedError(headers={"Retry-After": "3600"})
    version_ok = db.scalar(
        select(LessonVersion.id).where(
            LessonVersion.id == body.lesson_version_id, LessonVersion.lesson_id == lesson.lesson_id
        )
    )
    if version_ok is None:
        raise InvalidReferenceError(details=[{"field": "lesson_version_id", "issue": "mismatch"}])
    if body.question_id is not None:
        question_ok = db.scalar(
            select(Question.id).where(
                Question.id == body.question_id,
                Question.lesson_version_id == body.lesson_version_id,
            )
        )
        if question_ok is None:
            raise InvalidReferenceError(details=[{"field": "question_id", "issue": "mismatch"}])
    message = (body.message or "").strip() or None
    feedback = ContentFeedback(
        user_id=user_id,
        lesson_id=lesson.lesson_id,
        lesson_version_id=body.lesson_version_id,
        question_id=body.question_id,
        kind=body.kind,
        message=message,
        status="open",
        created_at=now,
    )
    db.add(feedback)
    db.commit()
    return feedback.id


def list_feedback(db: Session, *, status: str | None = "open") -> list[tuple[ContentFeedback, str]]:
    stmt = (
        select(ContentFeedback, Lesson.slug)
        .join(Lesson, Lesson.id == ContentFeedback.lesson_id)
        .order_by(ContentFeedback.created_at)
    )
    if status is not None:
        stmt = stmt.where(ContentFeedback.status == status)
    return [(row, slug) for row, slug in db.execute(stmt)]


def resolve_feedback(
    db: Session, feedback_id: uuid.UUID, *, dismiss: bool, note: str | None, now: datetime
) -> None:
    row = db.get(ContentFeedback, feedback_id)
    if row is None:
        raise LookupError(f"feedback {feedback_id} not found")
    row.status = "dismissed" if dismiss else "resolved"
    row.resolution_note = note
    row.resolved_at = now
    db.commit()
