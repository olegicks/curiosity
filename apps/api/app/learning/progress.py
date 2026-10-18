"""Per-user lesson progress shown on lesson cards (docs/spec/07 §7.2)."""

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.learning.models import LessonAttempt, UserLessonProgress
from app.reviews.models import ReviewState
from app.reviews.scheduler import mastery_stage

ProgressStatus = Literal[
    "not_started", "started", "completed", "recalled", "understood", "retained"
]
_STATUS_BY_STAGE: dict[int, ProgressStatus] = {
    1: "completed",
    2: "recalled",
    3: "understood",
    4: "retained",
}


class ProgressBrief(BaseModel):
    status: ProgressStatus
    mastery_stage: Literal[0, 1, 2, 3, 4]
    completed_at: datetime | None
    next_review_on: date | None
    in_progress_attempt_id: uuid.UUID | None


NOT_STARTED = ProgressBrief(
    status="not_started",
    mastery_stage=0,
    completed_at=None,
    next_review_on=None,
    in_progress_attempt_id=None,
)


def derive_progress(
    progress: UserLessonProgress | None,
    review: ReviewState | None,
    open_attempt_id: uuid.UUID | None,
) -> ProgressBrief:
    """Current state; it can go down after a failed review (milestones never do)."""
    if progress is None:
        return NOT_STARTED
    completed = progress.first_completed_at is not None
    stage = mastery_stage(completed=completed, repetitions=review.repetitions if review else 0)
    return ProgressBrief(
        status=_STATUS_BY_STAGE[stage] if completed else "started",
        mastery_stage=stage,
        completed_at=progress.first_completed_at,
        next_review_on=review.due_on if review else None,
        in_progress_attempt_id=open_attempt_id,
    )


def progress_briefs(
    db: Session, user_id: uuid.UUID, lesson_ids: list[uuid.UUID]
) -> dict[uuid.UUID, ProgressBrief]:
    if not lesson_ids:
        return {}
    progress = {
        p.lesson_id: p
        for p in db.scalars(
            select(UserLessonProgress).where(
                UserLessonProgress.user_id == user_id,
                UserLessonProgress.lesson_id.in_(lesson_ids),
            )
        )
    }
    reviews = {
        r.lesson_id: r
        for r in db.scalars(
            select(ReviewState).where(
                ReviewState.user_id == user_id, ReviewState.lesson_id.in_(lesson_ids)
            )
        )
    }
    open_attempts = {
        lesson_id: attempt_id
        for lesson_id, attempt_id in db.execute(
            select(LessonAttempt.lesson_id, LessonAttempt.id).where(
                LessonAttempt.user_id == user_id,
                LessonAttempt.lesson_id.in_(lesson_ids),
                LessonAttempt.status == "in_progress",
            )
        )
    }
    return {
        lesson_id: derive_progress(
            progress.get(lesson_id), reviews.get(lesson_id), open_attempts.get(lesson_id)
        )
        for lesson_id in lesson_ids
    }
