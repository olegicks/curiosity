"""Per-user lesson progress shown on lesson cards (docs/spec/07 §7.2).

Attempts and review states arrive with the learning and review modules; until
then every lesson is reported as not started.
"""

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel
from sqlalchemy.orm import Session

ProgressStatus = Literal[
    "not_started", "started", "completed", "recalled", "understood", "retained"
]


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


def progress_briefs(
    db: Session, user_id: uuid.UUID, lesson_ids: list[uuid.UUID]
) -> dict[uuid.UUID, ProgressBrief]:
    del db, user_id  # used once attempts and review states exist
    return dict.fromkeys(lesson_ids, NOT_STARTED)
