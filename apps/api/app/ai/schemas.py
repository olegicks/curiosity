"""AI explanation request/response models (docs/spec/05 §5.8)."""

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.ai.prompts import Mode


class ExplanationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Mode
    lesson_version_id: uuid.UUID
    exclude_ids: list[uuid.UUID] = Field(default_factory=list, max_length=10)


class ExplanationOut(BaseModel):
    id: uuid.UUID
    mode: Mode
    content: str
    label: Literal["ai_generated", "ai_reviewed"]
    variant: int
    has_more_variants: bool


class UsageOut(BaseModel):
    remaining_today: int
    limit_per_day: int


class ExplanationResponse(BaseModel):
    explanation: ExplanationOut
    usage: UsageOut


class FeedbackIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rating: Literal["helpful", "not_helpful", "incorrect"]
