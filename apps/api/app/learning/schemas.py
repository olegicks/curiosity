"""Lesson attempt request/response models (docs/spec/05 §5.5)."""

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.content.schemas import LessonContent, LessonSummary
from app.gamification.schemas import AchievementOut, StreakOut, XpAwardOut, XpSummaryOut


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class StartAttemptIn(StrictModel):
    restart: bool = False


class AnswerIn(StrictModel):
    """Options for choice questions, or `value` for an estimate question."""

    question_id: uuid.UUID
    selected_option_ids: list[uuid.UUID] = Field(default_factory=list, max_length=6)
    value: float | None = Field(default=None, allow_inf_nan=False)

    @model_validator(mode="after")
    def one_kind_of_answer(self) -> "AnswerIn":
        if bool(self.selected_option_ids) == (self.value is not None):
            raise ValueError("send selected_option_ids or value, not both or neither")
        return self


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
    estimate: "EstimateResultOut | None" = None


class EstimateResultOut(BaseModel):
    value: float
    answer: float
    tolerance: float
    unit: str


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


class ReviewActionOut(BaseModel):
    due_count: int
    estimated_minutes: int
    open_session_id: uuid.UUID | None


class PrimaryActionOut(BaseModel):
    type: Literal["review", "continue_lesson", "start_lesson", "caught_up"]
    review: ReviewActionOut | None = None
    lesson: LessonSummary | None = None
    attempt_id: uuid.UUID | None = None
    next_review_on: date | None = None


class DiscoverProgressOut(BaseModel):
    lessons_total: int
    completed: int
    understood: int


class DiscoverXpOut(BaseModel):
    today: int
    goal: int
    total: int


class DiscoverOut(BaseModel):
    local_date: date
    primary_action: PrimaryActionOut
    todays_lesson: LessonSummary | None
    recommended: list[LessonSummary]
    progress: DiscoverProgressOut
    streak: StreakOut
    xp: DiscoverXpOut
    reviews_due: int


class RatingIn(StrictModel):
    rating: Literal["clear", "unclear"]


class ContentFeedbackIn(StrictModel):
    kind: Literal["factual_error", "unclear", "typo", "other"]
    message: str | None = Field(default=None, max_length=500)
    question_id: uuid.UUID | None = None
    lesson_version_id: uuid.UUID


class ContentFeedbackOut(BaseModel):
    id: uuid.UUID
