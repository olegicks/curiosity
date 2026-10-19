"""POST /v1/events (docs/spec/05 §5.9)."""

from datetime import datetime

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.analytics.events import EventsAcceptedOut, EventsIn, ingest
from app.auth.deps import get_current_user, get_now, rate_limit
from app.auth.models import User
from app.core.db import get_db
from app.core.middleware import APP_VERSION_HEADER
from app.core.ratelimit import RateRule

router = APIRouter(tags=["analytics"])

EVENTS_PER_USER = RateRule("events_user", 60, 3600)


@router.post("/events", response_model=EventsAcceptedOut, status_code=status.HTTP_202_ACCEPTED)
def post_events(
    request: Request,
    body: EventsIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
) -> EventsAcceptedOut:
    rate_limit(request, EVENTS_PER_USER, str(user.id), now)
    return ingest(
        db,
        user.id,
        body.events,
        now=now,
        platform=request.headers.get("X-Platform"),
        app_version=request.headers.get(APP_VERSION_HEADER),
    )
