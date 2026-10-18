"""Profile, preferences and account deletion (docs/spec/05 §5.3, 09 §9.6)."""

import uuid
from datetime import datetime
from functools import lru_cache
from zoneinfo import available_timezones

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.auth.errors import InvalidCredentialsError
from app.auth.models import User
from app.core.errors import ValidationError
from app.core.security import verify_password
from app.users.models import UserPreferences
from app.users.schemas import PreferencesOut, PreferencesPatchIn

DELETE_CONFIRMATION = "DELETE"


class InvalidTimezoneError(ValidationError):
    code = "INVALID_TIMEZONE"
    message = "Unknown timezone."


class UnknownTopicError(ValidationError):
    code = "UNKNOWN_TOPIC"
    message = "Unknown topic."


class ConfirmationRequiredError(ValidationError):
    code = "CONFIRMATION_REQUIRED"
    message = "Type DELETE to confirm."


@lru_cache(maxsize=1)
def _timezones() -> frozenset[str]:
    return frozenset(available_timezones())


def is_valid_timezone(name: str) -> bool:
    return name in _timezones()


def timezone_or_utc(name: str | None) -> str:
    return name if name and is_valid_timezone(name) else "UTC"


def create_default_preferences(db: Session, user_id: uuid.UUID, timezone: str | None) -> None:
    db.add(UserPreferences(user_id=user_id, timezone=timezone_or_utc(timezone)))


def get_preferences(db: Session, user_id: uuid.UUID) -> UserPreferences:
    prefs = db.get(UserPreferences, user_id)
    if prefs is None:  # defensive: every user gets a row at creation
        prefs = UserPreferences(user_id=user_id)
        db.add(prefs)
        db.flush()
    return prefs


def preferences_out(prefs: UserPreferences) -> PreferencesOut:
    return PreferencesOut(
        timezone=prefs.timezone,
        daily_xp_goal=prefs.daily_xp_goal,
        interest_topics=[],  # topic interests arrive with the content module
        onboarding_completed=prefs.onboarding_completed_at is not None,
    )


def update_preferences(
    db: Session, user_id: uuid.UUID, patch: PreferencesPatchIn, now: datetime
) -> UserPreferences:
    prefs = get_preferences(db, user_id)
    if patch.timezone is not None:
        if not is_valid_timezone(patch.timezone):
            raise InvalidTimezoneError(details=[{"field": "timezone", "issue": "unknown"}])
        prefs.timezone = patch.timezone
    if patch.daily_xp_goal is not None:
        prefs.daily_xp_goal = patch.daily_xp_goal
    if patch.interest_topics:
        # No topics exist until the content module is imported, so any slug is unknown.
        raise UnknownTopicError(details=[{"field": "interest_topics", "issue": "unknown"}])
    if patch.onboarding_completed and prefs.onboarding_completed_at is None:
        prefs.onboarding_completed_at = now
    db.commit()
    return prefs


def update_display_name(db: Session, user: User, display_name: str | None) -> User:
    user.display_name = display_name
    db.commit()
    return user


def delete_account(db: Session, user: User, *, password: str | None, confirm: str | None) -> None:
    """Hard-delete the user; personal rows go with it via ON DELETE CASCADE."""
    if user.is_guest:
        if confirm != DELETE_CONFIRMATION:
            raise ConfirmationRequiredError(details=[{"field": "confirm", "issue": "required"}])
    elif (
        not password or not user.password_hash or not verify_password(user.password_hash, password)
    ):
        raise InvalidCredentialsError("Password is incorrect.")
    db.execute(delete(User).where(User.id == user.id))
    db.commit()
