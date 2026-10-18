"""Auth request/response models (docs/spec/05 §5.2)."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.users.schemas import normalize_display_name


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


def normalize_email(value: str) -> str:
    return value.strip().lower()


class GuestIn(StrictModel):
    timezone: str | None = Field(default=None, max_length=64)


class CredentialsIn(StrictModel):
    email: EmailStr = Field(max_length=254)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email", mode="after")
    @classmethod
    def _normalize_email(cls, value: str) -> str:
        return normalize_email(value)


class NewAccountIn(CredentialsIn):
    display_name: str | None = Field(default=None, max_length=60)

    @field_validator("display_name", mode="after")
    @classmethod
    def _normalize_display_name(cls, value: str | None) -> str | None:
        return normalize_display_name(value)


class RegisterIn(NewAccountIn):
    timezone: str | None = Field(default=None, max_length=64)


class UpgradeIn(NewAccountIn):
    pass


class LoginIn(CredentialsIn):
    pass


class RefreshIn(StrictModel):
    refresh_token: str = Field(min_length=1, max_length=256)


class LogoutIn(RefreshIn):
    pass


class PasswordChangeIn(StrictModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=1, max_length=128)


class TokensOut(BaseModel):
    access_token: str
    access_expires_in: int
    refresh_token: str
    token_type: Literal["Bearer"] = "Bearer"  # noqa: S105 - not a secret


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    is_guest: bool
    email: str | None
    display_name: str | None
    created_at: datetime


class AuthOut(BaseModel):
    user: UserOut
    tokens: TokensOut


class TokensResponse(BaseModel):
    tokens: TokensOut
