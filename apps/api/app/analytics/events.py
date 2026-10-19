"""Product events: whitelisted client events and server-side facts (docs/spec/12 §12.2).

No third-party analytics. Events are stored in Postgres and deleted with the account,
except ``account_deleted``, which is written without a user id.
"""

import json
import uuid
from datetime import datetime, timedelta
from typing import Any, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.orm import Session

from app.analytics.models import ProductEvent
from app.core.clock import to_local_date
from app.users.service import get_preferences

MAX_PROPERTIES_BYTES = 2048
MAX_PAST = timedelta(days=7)
MAX_FUTURE = timedelta(minutes=5)
PLATFORMS = ("ios", "android")


class _Props(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)  # unknown keys are dropped


class AppOpened(_Props):
    cold_start: bool


class ScreenViewed(_Props):
    screen: Literal["discover", "learn", "recall", "lesson_intro", "profile", "settings"]


class OnboardingStep(_Props):
    step: Literal["interests", "goal"]
    action: Literal["continue", "skip"]


class LessonStepViewed(_Props):
    attempt_id: uuid.UUID
    step_index: int = Field(ge=0, le=100)
    step_type: Literal[
        "hook", "explanation", "example", "misconception", "evidence", "question", "summary"
    ]


class AiSheetOpened(_Props):
    lesson_slug: str = Field(max_length=60)
    step_type: Literal["explanation", "example"]


class UpgradePrompt(_Props):
    action: Literal["shown", "accepted", "dismissed"]
    trigger: Literal["first_lesson", "third_lesson", "profile"]


class ReviewSessionClosed(_Props):
    session_id: uuid.UUID
    answered: int = Field(ge=0, le=100)
    total: int = Field(ge=0, le=100)


CLIENT_EVENTS: dict[str, type[_Props]] = {
    "app_opened": AppOpened,
    "screen_viewed": ScreenViewed,
    "onboarding_step": OnboardingStep,
    "lesson_step_viewed": LessonStepViewed,
    "ai_sheet_opened": AiSheetOpened,
    "upgrade_prompt": UpgradePrompt,
    "review_session_closed": ReviewSessionClosed,
}


class EventIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=64)
    occurred_at: AwareDatetime
    properties: dict[str, Any] = Field(default_factory=dict)


class EventsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    events: list[EventIn] = Field(min_length=1, max_length=20)


class EventsAcceptedOut(BaseModel):
    accepted: int
    rejected: int


def ingest(
    db: Session,
    user_id: uuid.UUID,
    events: list[EventIn],
    *,
    now: datetime,
    platform: str | None,
    app_version: str | None,
) -> EventsAcceptedOut:
    timezone = get_preferences(db, user_id).timezone
    platform = platform if platform in PLATFORMS else None
    app_version = app_version[:20] if app_version else None
    accepted = 0
    for event in events:
        model = CLIENT_EVENTS.get(event.name)
        if model is None:
            continue
        try:
            properties = model.model_validate(event.properties).model_dump(mode="json")
        except PydanticValidationError:
            continue
        if len(json.dumps(properties)) > MAX_PROPERTIES_BYTES:
            continue
        occurred = min(max(event.occurred_at, now - MAX_PAST), now + MAX_FUTURE)
        db.add(
            ProductEvent(
                user_id=user_id,
                name=event.name,
                properties=properties,
                occurred_at=occurred,
                received_at=now,
                local_date=to_local_date(occurred, timezone),
                platform=platform,
                app_version=app_version,
            )
        )
        accepted += 1
    db.commit()
    return EventsAcceptedOut(accepted=accepted, rejected=len(events) - accepted)
