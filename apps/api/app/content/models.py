"""Runtime copy of the canonical content (docs/spec/04 §4.3). Written only by the importer."""

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    UniqueConstraint,
)
from sqlalchemy import Text as SAText
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, CreatedAtMixin, TimestampMixin
from app.core.ids import uuid7


class Subject(TimestampMixin, Base):
    __tablename__ = "subjects"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    slug: Mapped[str] = mapped_column(SAText, nullable=False, unique=True)
    title: Mapped[str] = mapped_column(SAText, nullable=False)
    description: Mapped[str] = mapped_column(SAText, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False)


class Topic(TimestampMixin, Base):
    __tablename__ = "topics"
    __table_args__ = (UniqueConstraint("subject_id", "slug"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subjects.id", ondelete="RESTRICT"), nullable=False
    )
    slug: Mapped[str] = mapped_column(SAText, nullable=False)
    title: Mapped[str] = mapped_column(SAText, nullable=False)
    description: Mapped[str] = mapped_column(SAText, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)


class Source(TimestampMixin, Base):
    __tablename__ = "sources"
    __table_args__ = (
        CheckConstraint(
            "type IN ('journal_article','book','book_chapter','institutional','dataset','other')",
            name="type_allowed",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    key: Mapped[str] = mapped_column(SAText, nullable=False, unique=True)
    type: Mapped[str] = mapped_column(SAText, nullable=False)
    citation: Mapped[str] = mapped_column(SAText, nullable=False)
    doi: Mapped[str | None] = mapped_column(SAText)
    url: Mapped[str | None] = mapped_column(SAText)
    peer_reviewed: Mapped[bool] = mapped_column(Boolean, nullable=False)


class Lesson(TimestampMixin, Base):
    __tablename__ = "lessons"
    __table_args__ = (
        CheckConstraint("status IN ('draft','published','retired')", name="status_allowed"),
        CheckConstraint(
            "status <> 'published' OR current_version_id IS NOT NULL",
            name="published_has_version",
        ),
        Index("ix_lessons_topic_id_position", "topic_id", "position"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    slug: Mapped[str] = mapped_column(SAText, nullable=False, unique=True)
    topic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("topics.id", ondelete="RESTRICT"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(SAText, nullable=False)
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("lesson_versions.id", ondelete="RESTRICT", use_alter=True),
    )


class LessonVersion(CreatedAtMixin, Base):
    __tablename__ = "lesson_versions"
    __table_args__ = (
        UniqueConstraint("lesson_id", "version"),
        CheckConstraint(
            "evidence_status IN ('established','mixed','contested')", name="evidence_allowed"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    lesson_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(SAText, nullable=False)
    description: Mapped[str] = mapped_column(SAText, nullable=False)
    learning_objective: Mapped[str] = mapped_column(SAText, nullable=False)
    estimated_minutes: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    evidence_status: Mapped[str] = mapped_column(SAText, nullable=False)
    body: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    last_reviewed_on: Mapped[date | None] = mapped_column(Date)
    reviewers: Mapped[list[str]] = mapped_column(ARRAY(SAText), nullable=False, server_default="{}")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Question(Base):
    __tablename__ = "questions"
    __table_args__ = (
        UniqueConstraint("lesson_version_id", "key"),
        CheckConstraint("role IN ('lesson','recall')", name="role_allowed"),
        CheckConstraint(
            "type IN ('single_choice','multi_select','true_false')", name="type_allowed"
        ),
        Index("ix_questions_lesson_version_id_role", "lesson_version_id", "role"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    lesson_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("lesson_versions.id", ondelete="CASCADE"), nullable=False
    )
    key: Mapped[str] = mapped_column(SAText, nullable=False)
    role: Mapped[str] = mapped_column(SAText, nullable=False)
    type: Mapped[str] = mapped_column(SAText, nullable=False)
    prompt: Mapped[str] = mapped_column(SAText, nullable=False)
    explanation: Mapped[str] = mapped_column(SAText, nullable=False)
    shuffle: Mapped[bool] = mapped_column(Boolean, nullable=False)
    position: Mapped[int] = mapped_column(SmallInteger, nullable=False)


class AnswerOption(Base):
    __tablename__ = "answer_options"
    __table_args__ = (UniqueConstraint("question_id", "key"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("questions.id", ondelete="CASCADE"), nullable=False
    )
    key: Mapped[str] = mapped_column(SAText, nullable=False)
    text: Mapped[str] = mapped_column(SAText, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    feedback: Mapped[str] = mapped_column(SAText, nullable=False)
    position: Mapped[int] = mapped_column(SmallInteger, nullable=False)


class LessonVersionSource(Base):
    __tablename__ = "lesson_version_sources"

    lesson_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("lesson_versions.id", ondelete="CASCADE"), primary_key=True
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sources.id", ondelete="RESTRICT"), primary_key=True
    )
    note: Mapped[str | None] = mapped_column(SAText)
    position: Mapped[int] = mapped_column(SmallInteger, nullable=False)


class LessonRelation(Base):
    __tablename__ = "lesson_relations"
    __table_args__ = (
        CheckConstraint("from_lesson_id <> to_lesson_id", name="not_self"),
        CheckConstraint("relation_type IN ('related','prerequisite')", name="type_allowed"),
    )

    from_lesson_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("lessons.id", ondelete="CASCADE"), primary_key=True
    )
    to_lesson_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("lessons.id", ondelete="CASCADE"), primary_key=True
    )
    relation_type: Mapped[str] = mapped_column(SAText, primary_key=True)
    position: Mapped[int] = mapped_column(SmallInteger, nullable=False)
