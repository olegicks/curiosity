"""Auth dependencies shared by every protected router."""

from datetime import datetime

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth import service
from app.auth.errors import FullAccountRequiredError
from app.auth.models import User
from app.config import Settings
from app.core.clock import Clock
from app.core.db import get_db
from app.core.errors import UnauthenticatedError
from app.core.ratelimit import RateLimiter, RateRule
from app.core.security import InvalidTokenError

_bearer = HTTPBearer(auto_error=False)


def get_settings_dep(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_clock(request: Request) -> Clock:
    clock: Clock = request.app.state.clock
    return clock


def get_now(clock: Clock = Depends(get_clock)) -> datetime:
    return clock.now()


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
    settings: Settings = Depends(get_settings_dep),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise UnauthenticatedError
    try:
        return service.authenticate(
            db, access_token=credentials.credentials, now=now, settings=settings
        )
    except InvalidTokenError:
        raise UnauthenticatedError from None


def require_full_account(user: User = Depends(get_current_user)) -> User:
    if user.is_guest:
        raise FullAccountRequiredError
    return user


def client_ip(request: Request) -> str:
    # uvicorn --proxy-headers rewrites request.client from trusted proxies only.
    return request.client.host if request.client else "unknown"


def rate_limit(request: Request, rule: RateRule, key: str, now: datetime) -> None:
    limiter: RateLimiter = request.app.state.rate_limiter
    limiter.hit(rule, key, now)
