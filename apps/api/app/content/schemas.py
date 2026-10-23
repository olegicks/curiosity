"""Content API models (docs/spec/05 §5.1, §5.4).

Question and option models deliberately have no correctness or feedback fields:
the answer key can only leave the server through answer results.
"""

import uuid
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from app.learning.progress import ProgressBrief


class TopicRef(BaseModel):
    slug: str
    title: str


class TopicOut(BaseModel):
    slug: str
    title: str
    description: str
    position: int
    lesson_count: int


class SubjectOut(BaseModel):
    slug: str
    title: str
    description: str
    topics: list[TopicOut]


class SubjectsOut(BaseModel):
    items: list[SubjectOut]


class LessonSummary(BaseModel):
    slug: str
    title: str
    description: str
    subject: TopicRef
    topic: TopicRef
    estimated_minutes: int
    evidence_status: Literal["established", "mixed", "contested"]
    position: int
    progress: ProgressBrief


class LessonPage(BaseModel):
    items: list[LessonSummary]
    next_cursor: str | None


class ImageOut(BaseModel):
    url: str
    alt: str
    caption: str | None


class SourceOut(BaseModel):
    key: str
    citation: str
    url: str | None
    doi: str | None


class HookOut(BaseModel):
    type: Literal["hook"]
    body: str
    image: ImageOut | None


class ExplanationStepOut(BaseModel):
    type: Literal["explanation"]
    title: str | None
    body: str
    image: ImageOut | None


class ExampleOut(BaseModel):
    type: Literal["example"]
    kind: Literal["illustrative", "research"]
    title: str | None
    body: str
    source_key: str | None


class MisconceptionOut(BaseModel):
    type: Literal["misconception"]
    myth: str
    correction: str


class EvidenceOut(BaseModel):
    type: Literal["evidence"]
    status: Literal["established", "debated"]
    body: str
    source_keys: list[str]


class QuestionStepOut(BaseModel):
    type: Literal["question"]
    question_id: uuid.UUID


class SummaryOut(BaseModel):
    type: Literal["summary"]
    points: list[str]


StepOut = Annotated[
    HookOut
    | ExplanationStepOut
    | ExampleOut
    | MisconceptionOut
    | EvidenceOut
    | QuestionStepOut
    | SummaryOut,
    Field(discriminator="type"),
]


class OptionOut(BaseModel):
    id: uuid.UUID
    text: str


class EstimateOut(BaseModel):
    """Slider settings for an estimate question. The answer is revealed only after grading."""

    min: float
    max: float
    step: float
    unit: str
    anchor: float | None


class QuestionOut(BaseModel):
    id: uuid.UUID
    type: Literal["single_choice", "multi_select", "true_false", "estimate"]
    prompt: str
    options: list[OptionOut]
    estimate: EstimateOut | None = None


class LessonContent(BaseModel):
    lesson_version_id: uuid.UUID
    version: int
    slug: str
    title: str
    learning_objective: str
    estimated_minutes: int
    evidence_status: Literal["established", "mixed", "contested"]
    steps: list[StepOut]
    questions: list[QuestionOut]
    sources: list[SourceOut]
    related: list[LessonSummary]


class LessonDetail(LessonSummary):
    learning_objective: str
    related: list[LessonSummary]


class LessonDetailOut(BaseModel):
    lesson: LessonDetail
    content: LessonContent
