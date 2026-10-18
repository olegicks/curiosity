"""Per-user preferences (docs/spec/04 §4.2)."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, SmallInteger
from sqlalchemy import Text as SAText
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin

DAILY_XP_GOALS = (20, 40, 60)
DEFAULT_DAILY_XP_GOAL = 20


class UserPreferences(TimestampMixin, Base):
    __tablename__ = "user_preferences"
    __table_args__ = (
        CheckConstraint("daily_xp_goal IN (20, 40, 60)", name="daily_xp_goal_allowed"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    timezone: Mapped[str] = mapped_column(SAText, nullable=False, server_default="UTC")
    daily_xp_goal: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default=str(DEFAULT_DAILY_XP_GOAL)
    )
    onboarding_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
