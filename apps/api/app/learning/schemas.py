"""Lesson attempt request/response models (docs/spec/05 §5.5)."""

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.content.schemas import LessonContent, LessonSummary
from app.gamification.schemas import AchievementOut, StreakOut, XpAwardOut, XpSummaryOut


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class StartAttemptIn(StrictModel):
    restart: bool = False


class AnswerIn(StrictModel):
    question_id: uuid.UUID
    selected_option_ids: list[uuid.UUID] = Field(min_length=1, max_length=6)


class OptionFeedbackOut(BaseModel):
    option_id: uuid.UUID
    is_correct: bool
    feedback: str


class AnswerResult(BaseModel):
    question_id: uuid.UUID
    is_correct: bool
    selected_option_ids: list[uuid.UUID]
    correct_option_ids: list[uuid.UUID]
    option_feedback: list[OptionFeedbackOut]
    explanation: str


class AnswerResponse(AnswerResult):
    replayed: bool


class AttemptOut(BaseModel):
    id: uuid.UUID
    status: Literal["in_progress", "completed", "abandoned"]
    lesson_version_id: uuid.UUID
    started_at: datetime
    answers: list[AnswerResult]
    is_revisit: bool


class AttemptResponse(BaseModel):
    attempt: AttemptOut
    content: LessonContent
    resumed: bool


class CompletedAttemptOut(BaseModel):
    id: uuid.UUID
    status: Literal["completed"]
    correct_first_try: int
    question_count: int
    is_first_completion: bool


class CompletionResponse(BaseModel):
    attempt: CompletedAttemptOut
    first_review_on: date | None
    next_lesson: LessonSummary | None
    xp_awarded: list[XpAwardOut]
    xp: XpSummaryOut
    streak: StreakOut
    achievements_unlocked: list[AchievementOut]
    replayed: bool
