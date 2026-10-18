"""Lesson attempts, answers and per-lesson progress milestones (docs/spec/04 §4.4)."""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    UniqueConstraint,
    text,
)
from sqlalchemy import Text as SAText
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.ids import uuid7


class LessonAttempt(Base):
    __tablename__ = "lesson_attempts"
    __table_args__ = (
        CheckConstraint("status IN ('in_progress','completed','abandoned')", name="status_allowed"),
        CheckConstraint(
            "(status = 'completed') = (completed_at IS NOT NULL)", name="completed_has_timestamp"
        ),
        # at most one open attempt per lesson
        Index(
            "uq_lesson_attempts_open",
            "user_id",
            "lesson_id",
            unique=True,
            postgresql_where=text("status = 'in_progress'"),
        ),
        # only one attempt can be the first completion (guards milestone + rewards)
        Index(
            "uq_lesson_attempts_first_completion",
            "user_id",
            "lesson_id",
            unique=True,
            postgresql_where=text("is_first_completion"),
        ),
        Index("ix_lesson_attempts_user_id_started_at", "user_id", "started_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    lesson_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("lessons.id", ondelete="RESTRICT"), nullable=False
    )
    lesson_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("lesson_versions.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(SAText, nullable=False)
    is_first_completion: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    correct_first_try: Mapped[int | None] = mapped_column(SmallInteger)
    question_count: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    local_date_completed: Mapped[date | None] = mapped_column(Date)


class LessonAttemptAnswer(Base):
    __tablename__ = "lesson_attempt_answers"
    __table_args__ = (UniqueConstraint("attempt_id", "question_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    attempt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("lesson_attempts.id", ondelete="CASCADE"), nullable=False
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("questions.id", ondelete="RESTRICT"), nullable=False
    )
    selected_option_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=False
    )
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    answered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class UserLessonProgress(Base):
    __tablename__ = "user_lesson_progress"
    __table_args__ = (
        CheckConstraint(
            "first_completed_at IS NULL OR first_completed_at >= first_started_at",
            name="completed_after_started",
        ),
        CheckConstraint(
            "first_recalled_at IS NULL OR first_completed_at IS NOT NULL",
            name="recalled_after_completed",
        ),
        CheckConstraint(
            "first_understood_at IS NULL OR first_recalled_at IS NOT NULL",
            name="understood_after_recalled",
        ),
        Index(
            "ix_user_lesson_progress_user_id_first_completed_at", "user_id", "first_completed_at"
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    lesson_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("lessons.id", ondelete="RESTRICT"), primary_key=True
    )
    first_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    first_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_recalled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_understood_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completion_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    first_attempt_score: Mapped[int | None] = mapped_column(SmallInteger)
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
