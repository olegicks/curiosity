"""Review request/response models (docs/spec/05 §5.6)."""

import uuid
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.content.schemas import QuestionOut
from app.learning.schemas import OptionFeedbackOut

MasteryStage = Literal[0, 1, 2, 3, 4]
SessionStatus = Literal["open", "completed", "ended_early", "expired"]


class ReviewSummaryOut(BaseModel):
    due_count: int
    next_due_on: date | None
    in_review_count: int
    open_session_id: uuid.UUID | None
    estimated_minutes: int


class LessonRef(BaseModel):
    slug: str
    title: str


class ConceptOut(BaseModel):
    lesson: LessonRef
    mastery_stage: MasteryStage
    due_on: date
    is_due: bool


class ConceptPage(BaseModel):
    items: list[ConceptOut]
    next_cursor: str | None


class ReviewAnswerIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selected_option_ids: list[uuid.UUID] = Field(min_length=1, max_length=6)
    guessed: bool = False


class ScheduleOut(BaseModel):
    previous_interval_days: int
    next_interval_days: int
    next_due_on: date


class StageChangeOut(BaseModel):
    before: MasteryStage
    after: MasteryStage


class ReviewAnswerResult(BaseModel):
    is_correct: bool
    quality: Literal[1, 3, 4]
    selected_option_ids: list[uuid.UUID]
    correct_option_ids: list[uuid.UUID]
    option_feedback: list[OptionFeedbackOut]
    explanation: str
    schedule: ScheduleOut
    mastery_stage: StageChangeOut


class SessionItemOut(BaseModel):
    id: uuid.UUID
    position: int
    lesson: LessonRef
    question: QuestionOut
    result: ReviewAnswerResult | None


class StageAdvanceOut(BaseModel):
    slug: str
    from_stage: MasteryStage = Field(serialization_alias="from")
    to_stage: MasteryStage = Field(serialization_alias="to")


class SessionSummaryOut(BaseModel):
    correct: int
    total: int
    advanced: list[StageAdvanceOut]
    to_revisit: list[LessonRef]


class SessionOut(BaseModel):
    id: uuid.UUID
    status: SessionStatus
    local_date: date
    item_count: int
    answered_count: int
    items: list[SessionItemOut]


class SessionResponse(BaseModel):
    session: SessionOut
    summary: SessionSummaryOut | None
    resumed: bool


class SessionProgressOut(BaseModel):
    answered_count: int
    item_count: int
    status: SessionStatus


class ReviewAnswerResponse(BaseModel):
    result: ReviewAnswerResult
    session: SessionProgressOut
    session_summary: SessionSummaryOut | None
    replayed: bool
