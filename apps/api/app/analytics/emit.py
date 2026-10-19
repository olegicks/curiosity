"""Server-side product events, written inside the caller's transaction.

Kept free of other app imports so any service can emit without import cycles.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.analytics.models import ProductEvent
from app.core.clock import to_local_date


def emit(
    db: Session,
    name: str,
    *,
    user_id: uuid.UUID | None,
    now: datetime,
    timezone: str | None,
    properties: dict[str, Any] | None = None,
) -> None:
    """Record a server-side fact inside the caller's transaction (no commit)."""
    db.add(
        ProductEvent(
            user_id=user_id,
            name=name,
            properties=properties or {},
            occurred_at=now,
            received_at=now,
            local_date=to_local_date(now, timezone),
        )
    )
