"""XP ledger, streak state, daily activity and earned achievements (docs/spec/04 §4.6)."""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    UniqueConstraint,
    func,
)
from sqlalchemy import Text as SAText
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, CreatedAtMixin
from app.core.ids import uuid7


class XpTransaction(CreatedAtMixin, Base):
    __tablename__ = "xp_transactions"
    __table_args__ = (
        UniqueConstraint("user_id", "idempotency_key"),
        CheckConstraint("amount > 0", name="amount_positive"),
        CheckConstraint(
            "reason IN ('lesson_complete','lesson_perfect','review_item','review_session',"
            "'daily_goal')",
            name="reason_allowed",
        ),
        Index("ix_xp_transactions_user_id_local_date", "user_id", "local_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(SAText, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(SAText, nullable=False)
    lesson_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("lessons.id", ondelete="RESTRICT")
    )
    # The request that caused the award, so replays can return the same XP breakdown.
    attempt_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("lesson_attempts.id", ondelete="CASCADE"), index=True
    )
    review_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("review_sessions.id", ondelete="CASCADE"), index=True
    )
    review_session_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("review_session_items.id", ondelete="CASCADE"), index=True
    )
    local_date: Mapped[date] = mapped_column(Date, nullable=False)


class StreakState(Base):
    __tablename__ = "streak_states"
    __table_args__ = (
        CheckConstraint("freezes_available BETWEEN 0 AND 2", name="freezes_range"),
        CheckConstraint("current_streak >= 0 AND longest_streak >= current_streak", name="counts"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    current_streak: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    longest_streak: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    last_streak_date: Mapped[date | None] = mapped_column(Date)
    freezes_available: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="1")
    freezes_used_total: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class DailyActivity(Base):
    __tablename__ = "daily_activity"
    __table_args__ = (
        CheckConstraint(
            "lesson_questions_answered >= 0 AND review_items_answered >= 0 AND "
            "lessons_completed >= 0 AND review_sessions_completed >= 0 AND xp_earned >= 0",
            name="counts_non_negative",
        ),
        Index("ix_daily_activity_local_date", "local_date"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    local_date: Mapped[date] = mapped_column(Date, primary_key=True)
    lesson_questions_answered: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    review_items_answered: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    lessons_completed: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    review_sessions_completed: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    xp_earned: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class UserAchievement(Base):
    __tablename__ = "user_achievements"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    code: Mapped[str] = mapped_column(SAText, primary_key=True)
    earned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # e.g. "attempt:<id>" or "review_item:<id>", so replays return the same unlocks
    source_key: Mapped[str] = mapped_column(SAText, nullable=False)
