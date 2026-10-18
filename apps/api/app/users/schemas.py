"""/me and preferences models (docs/spec/05 §5.3)."""

import unicodedata
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

DISPLAY_NAME_MAX = 40


def normalize_display_name(value: str | None) -> str | None:
    """Trim; reject empty, over-long, or control-character names."""
    if value is None:
        return None
    name = value.strip()
    if not name:
        raise ValueError("display name must not be empty")
    if len(name) > DISPLAY_NAME_MAX:
        raise ValueError(f"display name must be at most {DISPLAY_NAME_MAX} characters")
    if any(unicodedata.category(ch).startswith("C") for ch in name):
        raise ValueError("display name contains control characters")
    return name


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MePatchIn(StrictModel):
    display_name: str | None = Field(max_length=60)

    @field_validator("display_name", mode="after")
    @classmethod
    def _normalize(cls, value: str | None) -> str | None:
        return normalize_display_name(value)


class PreferencesOut(BaseModel):
    timezone: str
    daily_xp_goal: Literal[20, 40, 60]
    interest_topics: list[str]
    onboarding_completed: bool


class PreferencesPatchIn(StrictModel):
    timezone: str | None = Field(default=None, max_length=64)
    daily_xp_goal: Literal[20, 40, 60] | None = None
    interest_topics: list[str] | None = Field(default=None, max_length=3)
    onboarding_completed: Literal[True] | None = None


class DeleteMeIn(StrictModel):
    password: str | None = Field(default=None, max_length=128)
    confirm: str | None = Field(default=None, max_length=16)
