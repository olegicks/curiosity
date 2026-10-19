"""In-house product events (docs/spec/04 §4.8, 12 §12.2)."""

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Identity, Index
from sqlalchemy import Text as SAText
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class ProductEvent(Base):
    __tablename__ = "product_events"
    __table_args__ = (
        Index("ix_product_events_name_occurred_at", "name", "occurred_at"),
        Index("ix_product_events_user_id_occurred_at", "user_id", "occurred_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    # NULL only for anonymised events such as account_deleted
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(SAText, nullable=False)
    properties: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    local_date: Mapped[date] = mapped_column(Date, nullable=False)
    platform: Mapped[str | None] = mapped_column(SAText)
    app_version: Mapped[str | None] = mapped_column(SAText)
