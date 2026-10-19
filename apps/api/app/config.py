"""Application settings, loaded from environment variables (see docs/spec/13-operations.md)."""

from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AiProvider(StrEnum):
    FAKE = "fake"
    ANTHROPIC = "anthropic"


class AppEnv(StrEnum):
    LOCAL = "local"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


def parse_version(value: str) -> tuple[int, int, int]:
    """Parse a strict MAJOR.MINOR.PATCH version string."""
    parts = value.strip().split(".")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        raise ValueError(f"invalid version {value!r}, expected MAJOR.MINOR.PATCH")
    major, minor, patch = (int(p) for p in parts)
    return major, minor, patch


def _default_content_dir() -> Path:
    """<repo>/content for a checkout (apps/api/app/config.py); /app/content in the image."""
    here = Path(__file__).resolve()
    candidates = [p / "content" for p in here.parents[1:4]]
    return next((c for c in candidates if c.is_dir()), candidates[0])


DEFAULT_CONTENT_DIR = _default_content_dir()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: AppEnv = AppEnv.LOCAL
    git_sha: str = "dev"

    database_url: str
    db_pool_size: int = Field(default=10, ge=1, le=100)
    db_connect_timeout_seconds: int = Field(default=5, ge=1, le=60)

    log_level: str = "INFO"
    min_app_version: str = "1.0.0"
    expose_openapi: bool | None = None

    jwt_secret: SecretStr
    access_token_ttl_seconds: int = Field(default=900, ge=60, le=3600)
    refresh_token_ttl_days: int = Field(default=30, ge=1, le=365)
    refresh_reuse_grace_seconds: int = Field(default=10, ge=0, le=60)
    rate_limit_enabled: bool = True

    content_dir: Path = DEFAULT_CONTENT_DIR
    content_allow_draft_overwrite: bool = False

    ai_explanations_enabled: bool = True
    ai_provider: AiProvider = AiProvider.FAKE
    anthropic_api_key: SecretStr | None = None
    ai_model: str = "claude-opus-5-5"
    ai_effort: Literal["low", "medium", "high"] = "low"
    ai_refusal_fallback: bool = True
    ai_timeout_seconds: float = Field(default=15.0, gt=0, le=60)
    ai_max_output_tokens: int = Field(default=1024, ge=256, le=4096)
    ai_max_variants: int = Field(default=3, ge=1, le=10)
    ai_user_daily_limit: int = Field(default=20, ge=1)
    ai_user_burst_limit: int = Field(default=5, ge=1)
    ai_daily_budget_micros: int = Field(default=5_000_000, ge=0)
    ai_price_input_per_mtok_micros: int | None = Field(default=None, ge=0)
    ai_price_output_per_mtok_micros: int | None = Field(default=None, ge=0)

    @field_validator("jwt_secret")
    @classmethod
    def _validate_jwt_secret(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value().encode()) < 32:
            raise ValueError("JWT_SECRET must be at least 32 bytes")
        return value

    @model_validator(mode="after")
    def _require_provider_key(self) -> "Settings":
        if (
            self.ai_explanations_enabled
            and self.ai_provider == AiProvider.ANTHROPIC
            and self.anthropic_api_key is None
        ):
            raise ValueError("ANTHROPIC_API_KEY is required when AI_PROVIDER=anthropic")
        return self

    @field_validator("min_app_version")
    @classmethod
    def _validate_min_app_version(cls, value: str) -> str:
        parse_version(value)
        return value

    @field_validator("log_level")
    @classmethod
    def _validate_log_level(cls, value: str) -> str:
        level = value.upper()
        if level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError(f"invalid log level {value!r}")
        return level

    @property
    def openapi_enabled(self) -> bool:
        if self.expose_openapi is not None:
            return self.expose_openapi
        return self.app_env != AppEnv.PRODUCTION

    @property
    def min_app_version_tuple(self) -> tuple[int, int, int]:
        return parse_version(self.min_app_version)


@lru_cache
def get_settings() -> Settings:
    return Settings()  # values come from the environment
