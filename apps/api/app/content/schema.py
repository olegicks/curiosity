"""Authoring schema for content YAML files (docs/spec/03 §3.2).

Field-level rules live on the models; rules that span fields or files are in
``rules.py``. The importer uses the same models, so what validates is what imports.
"""

import re
import uuid
from datetime import date
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

SLUG_PATTERN = r"^[a-z0-9]+(-[a-z0-9]+)*$"
KEY_PATTERN = r"^[a-z0-9-]+$"

Slug = Annotated[str, StringConstraints(pattern=SLUG_PATTERN, max_length=60)]
Key = Annotated[str, StringConstraints(pattern=KEY_PATTERN, max_length=60)]
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


def word_count(text: str) -> int:
    return len(re.findall(r"\S+", text))


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


# --- subjects and topics -------------------------------------------------------------


class TopicIn(Strict):
    slug: Slug
    title: Annotated[Text, StringConstraints(max_length=80)]
    description: Annotated[Text, StringConstraints(max_length=200)]
    position: int = Field(ge=0)


class SubjectIn(Strict):
    slug: Slug
    title: Annotated[Text, StringConstraints(max_length=80)]
    description: Annotated[Text, StringConstraints(max_length=300)]
    position: int = Field(ge=0)
    published: bool
    topics: list[TopicIn] = Field(min_length=1)


class SubjectsFile(Strict):
    subjects: list[SubjectIn] = Field(min_length=1)


# --- sources -------------------------------------------------------------------------


class SourceType(StrEnum):
    JOURNAL_ARTICLE = "journal_article"
    BOOK = "book"
    BOOK_CHAPTER = "book_chapter"
    INSTITUTIONAL = "institutional"
    DATASET = "dataset"
    OTHER = "other"


class SourceIn(Strict):
    key: Key
    type: SourceType
    citation: Annotated[Text, StringConstraints(max_length=500)]
    doi: str | None = Field(default=None, max_length=200)
    url: Annotated[str, StringConstraints(pattern=r"^https://", max_length=500)] | None = None
    peer_reviewed: bool


class SourcesFile(Strict):
    sources: list[SourceIn]


# --- lessons -------------------------------------------------------------------------


class LessonStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    RETIRED = "retired"


class EvidenceStatus(StrEnum):
    ESTABLISHED = "established"
    MIXED = "mixed"
    CONTESTED = "contested"


class ImageIn(Strict):
    file: Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9._-]*\.(png|webp)$")]
    alt: Annotated[Text, StringConstraints(max_length=200)]
    caption: Annotated[Text, StringConstraints(max_length=200)] | None = None


class HookStep(Strict):
    type: Literal["hook"]
    body: Text
    image: ImageIn | None = None


class ExplanationStep(Strict):
    type: Literal["explanation"]
    title: Annotated[Text, StringConstraints(max_length=80)] | None = None
    body: Text
    image: ImageIn | None = None


class ExampleStep(Strict):
    type: Literal["example"]
    kind: Literal["illustrative", "research"]
    title: Annotated[Text, StringConstraints(max_length=80)] | None = None
    body: Text
    source_key: Key | None = None


class MisconceptionStep(Strict):
    type: Literal["misconception"]
    myth: Annotated[Text, StringConstraints(max_length=300)]
    correction: Text


class EvidenceStep(Strict):
    type: Literal["evidence"]
    status: Literal["established", "debated"]
    body: Text
    source_keys: list[Key] = Field(min_length=1)


class QuestionStep(Strict):
    type: Literal["question"]
    question_key: Key


class SummaryStep(Strict):
    type: Literal["summary"]
    points: list[Text] = Field(min_length=2, max_length=4)


Step = Annotated[
    HookStep
    | ExplanationStep
    | ExampleStep
    | MisconceptionStep
    | EvidenceStep
    | QuestionStep
    | SummaryStep,
    Field(discriminator="type"),
]


class QuestionRole(StrEnum):
    LESSON = "lesson"
    RECALL = "recall"


class QuestionType(StrEnum):
    SINGLE_CHOICE = "single_choice"
    MULTI_SELECT = "multi_select"
    TRUE_FALSE = "true_false"


class OptionIn(Strict):
    key: Key
    text: Annotated[Text, StringConstraints(max_length=160)]
    correct: bool
    feedback: Annotated[Text, StringConstraints(max_length=280)]


class QuestionIn(Strict):
    key: Key
    role: QuestionRole
    type: QuestionType
    prompt: Annotated[Text, StringConstraints(max_length=300)]
    options: list[OptionIn] = Field(min_length=2, max_length=6)
    explanation: Annotated[Text, StringConstraints(max_length=400)]
    shuffle: bool = True


class SourceRef(Strict):
    key: Key
    note: Annotated[Text, StringConstraints(max_length=200)] | None = None


class ChangelogEntry(Strict):
    version: int = Field(ge=1)
    date: date
    summary: Annotated[Text, StringConstraints(max_length=300)]


class LessonFile(Strict):
    id: uuid.UUID
    slug: Slug
    version: int = Field(ge=1)
    status: LessonStatus
    subject: Slug
    topic: Slug
    position: int = Field(ge=0)
    title: Annotated[Text, StringConstraints(max_length=60)]
    description: Annotated[Text, StringConstraints(max_length=140)]
    learning_objective: Annotated[Text, StringConstraints(max_length=200)]
    estimated_minutes: int = Field(ge=3, le=10)
    evidence_status: EvidenceStatus
    last_reviewed_on: date | None = None
    reviewers: list[Annotated[Text, StringConstraints(max_length=80)]] = Field(default_factory=list)
    prerequisites: list[Slug] = Field(default_factory=list)
    related: list[Slug] = Field(default_factory=list, max_length=4)
    sources: list[SourceRef] = Field(default_factory=list)
    steps: list[Step] = Field(min_length=1)
    questions: list[QuestionIn] = Field(min_length=1)
    changelog: list[ChangelogEntry] = Field(default_factory=list)

    def content_payload(self) -> dict[str, object]:
        """Fields that define a version's content. Editorial metadata and lesson-level
        relations (rewritten on every import) are excluded from the hash."""
        return self.model_dump(
            mode="json",
            exclude={
                "status",
                "position",
                "last_reviewed_on",
                "reviewers",
                "changelog",
                "related",
                "prerequisites",
            },
        )
