"""Current review schedule per user and concept (docs/spec/04 §4.5)."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, Numeric
from sqlalchemy import Text as SAText
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin


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
