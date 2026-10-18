"""Identity tables: users and refresh tokens (docs/spec/04 §4.2)."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, LargeBinary
from sqlalchemy import Text as SAText
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, CreatedAtMixin, TimestampMixin
from app.core.ids import uuid7


class User(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "is_guest OR (email IS NOT NULL AND password_hash IS NOT NULL)",
            name="full_account_has_credentials",
        ),
        CheckConstraint(
            "NOT is_guest OR (email IS NULL AND password_hash IS NULL)",
            name="guest_has_no_credentials",
        ),
        CheckConstraint("email = lower(email)", name="email_lowercase"),
        Index("ix_users_is_guest_last_seen_at", "is_guest", "last_seen_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    # Stored normalised (trimmed, lowercased); see docs/spec/15 deviations (no citext).
    email: Mapped[str | None] = mapped_column(SAText, unique=True)
    password_hash: Mapped[str | None] = mapped_column(SAText)
    display_name: Mapped[str | None] = mapped_column(SAText)
    is_guest: Mapped[bool] = mapped_column(Boolean, nullable=False)
    is_internal: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    token_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    upgraded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RefreshToken(CreatedAtMixin, Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    family_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    token_hash: Mapped[bytes] = mapped_column(LargeBinary, nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
