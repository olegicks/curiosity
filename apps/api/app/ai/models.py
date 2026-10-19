"""Shared explanation cache, usage log and feedback (docs/spec/04 §4.7)."""

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    UniqueConstraint,
)
from sqlalchemy import Text as SAText
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, CreatedAtMixin
from app.core.ids import uuid7

MODES_SQL = "('simpler','example','analogy')"


class AiExplanation(CreatedAtMixin, Base):
    """A generated explanation for (lesson version, mode, prompt version); no user data."""

    __tablename__ = "ai_explanations"
    __table_args__ = (
        UniqueConstraint("lesson_version_id", "mode", "prompt_version", "variant"),
        CheckConstraint(f"mode IN {MODES_SQL}", name="mode_allowed"),
        CheckConstraint(
            "status IN ('generated','approved','hidden','rejected')", name="status_allowed"
        ),
        CheckConstraint("variant >= 1", name="variant_positive"),
        Index("ix_ai_explanations_lookup", "lesson_version_id", "mode", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    lesson_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("lesson_versions.id", ondelete="CASCADE"), nullable=False
    )
    mode: Mapped[str] = mapped_column(SAText, nullable=False)
    variant: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    prompt_version: Mapped[str] = mapped_column(SAText, nullable=False)
    model: Mapped[str] = mapped_column(SAText, nullable=False)
    content: Mapped[str] = mapped_column(SAText, nullable=False)
    status: Mapped[str] = mapped_column(SAText, nullable=False)
    flag_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    cost_micros: Mapped[int] = mapped_column(BigInteger, nullable=False)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AiRequest(Base):
    """One user request for an explanation. Holds no content; kept after account deletion."""

    __tablename__ = "ai_requests"
    __table_args__ = (
        CheckConstraint(f"mode IN {MODES_SQL}", name="mode_allowed"),
        CheckConstraint(
            "outcome IN ('cache_hit','generated','rate_limited','budget_exceeded','disabled',"
            "'provider_error','timeout','invalid_output')",
            name="outcome_allowed",
        ),
        Index("ix_ai_requests_user_id_created_at", "user_id", "created_at"),
        Index("ix_ai_requests_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    lesson_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("lesson_versions.id", ondelete="CASCADE"), nullable=False
    )
    mode: Mapped[str] = mapped_column(SAText, nullable=False)
    explanation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_explanations.id", ondelete="SET NULL")
    )
    outcome: Mapped[str] = mapped_column(SAText, nullable=False)
    model: Mapped[str | None] = mapped_column(SAText)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    cost_micros: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AiExplanationFeedback(CreatedAtMixin, Base):
    __tablename__ = "ai_explanation_feedback"
    __table_args__ = (
        CheckConstraint("rating IN ('helpful','not_helpful','incorrect')", name="rating_allowed"),
    )

    explanation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_explanations.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    rating: Mapped[str] = mapped_column(SAText, nullable=False)
