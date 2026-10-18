"""Review schedule, sessions and history (docs/spec/04 §4.5)."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    UniqueConstraint,
    text,
)
from sqlalchemy import Text as SAText
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, CreatedAtMixin, TimestampMixin
from app.core.ids import uuid7


class ReviewState(TimestampMixin, Base):
    __tablename__ = "review_states"
    __table_args__ = (
        CheckConstraint("ease_factor BETWEEN 1.30 AND 2.80", name="ease_factor_range"),
        CheckConstraint("interval_days BETWEEN 1 AND 180", name="interval_range"),
        CheckConstraint("repetitions >= 0", name="repetitions_non_negative"),
        CheckConstraint("lapses >= 0", name="lapses_non_negative"),
        Index("ix_review_states_user_id_due_on", "user_id", "due_on"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    lesson_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("lessons.id", ondelete="RESTRICT"), primary_key=True
    )
    scheduler_version: Mapped[str] = mapped_column(SAText, nullable=False)
    ease_factor: Mapped[Decimal] = mapped_column(Numeric(3, 2), nullable=False)
    interval_days: Mapped[int] = mapped_column(Integer, nullable=False)
    repetitions: Mapped[int] = mapped_column(Integer, nullable=False)
    lapses: Mapped[int] = mapped_column(Integer, nullable=False)
    due_on: Mapped[date] = mapped_column(Date, nullable=False)
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_question_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("questions.id", ondelete="SET NULL")
    )


class ReviewSession(CreatedAtMixin, Base):
    __tablename__ = "review_sessions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('open','completed','ended_early','expired')", name="status_allowed"
        ),
        # one open session per user
        Index(
            "uq_review_sessions_open",
            "user_id",
            unique=True,
            postgresql_where=text("status = 'open'"),
        ),
        Index("ix_review_sessions_user_id_created_at", "user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    local_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(SAText, nullable=False)
    item_count: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ReviewSessionItem(Base):
    __tablename__ = "review_session_items"
    __table_args__ = (
        UniqueConstraint("session_id", "lesson_id"),
        UniqueConstraint("session_id", "position"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("review_sessions.id", ondelete="CASCADE"), nullable=False
    )
    lesson_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("lessons.id", ondelete="RESTRICT"), nullable=False
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("questions.id", ondelete="RESTRICT"), nullable=False
    )
    position: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ReviewEvent(Base):
    """One answered review item with the schedule before and after (review history)."""

    __tablename__ = "review_events"
    __table_args__ = (
        CheckConstraint("quality IN (1, 3, 4)", name="quality_allowed"),
        Index("ix_review_events_user_id_answered_at", "user_id", "answered_at"),
        Index("ix_review_events_lesson_id_question_id", "lesson_id", "question_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    session_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("review_session_items.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    lesson_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("lessons.id", ondelete="RESTRICT"), nullable=False
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("questions.id", ondelete="RESTRICT"), nullable=False
    )
    selected_option_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=False
    )
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    guessed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    quality: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    scheduler_version: Mapped[str] = mapped_column(SAText, nullable=False)
    ef_before: Mapped[Decimal] = mapped_column(Numeric(3, 2), nullable=False)
    ef_after: Mapped[Decimal] = mapped_column(Numeric(3, 2), nullable=False)
    interval_before: Mapped[int] = mapped_column(Integer, nullable=False)
    interval_after: Mapped[int] = mapped_column(Integer, nullable=False)
    reps_before: Mapped[int] = mapped_column(Integer, nullable=False)
    reps_after: Mapped[int] = mapped_column(Integer, nullable=False)
    due_on_before: Mapped[date] = mapped_column(Date, nullable=False)
    due_on_after: Mapped[date] = mapped_column(Date, nullable=False)
    days_since_last_review: Mapped[int] = mapped_column(Integer, nullable=False)
    review_number: Mapped[int] = mapped_column(Integer, nullable=False)
    local_date: Mapped[date] = mapped_column(Date, nullable=False)
    answered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
