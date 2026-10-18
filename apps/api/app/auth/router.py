"""/v1/auth/* and /v1/me/password (docs/spec/05 §5.2)."""

from datetime import datetime

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.auth import service
from app.auth.deps import (
    client_ip,
    get_current_user,
    get_now,
    get_settings_dep,
    rate_limit,
    require_full_account,
)
from app.auth.models import User
from app.auth.schemas import (
    AuthOut,
    GuestIn,
    LoginIn,
    LogoutIn,
    PasswordChangeIn,
    RefreshIn,
    RegisterIn,
    TokensResponse,
    UpgradeIn,
    UserOut,
)
from app.config import Settings
from app.core.db import get_db
from app.core.ratelimit import RateRule

router = APIRouter(tags=["auth"])

HOUR = 3600
GUEST_PER_IP = RateRule("guest_ip", 10, HOUR)
REGISTER_PER_IP = RateRule("register_ip", 5, HOUR)
LOGIN_PER_ACCOUNT_MINUTE = RateRule("login_account_min", 5, 60)
LOGIN_PER_ACCOUNT_HOUR = RateRule("login_account_hour", 20, HOUR)
LOGIN_PER_IP = RateRule("login_ip", 50, HOUR)
PASSWORD_CHANGE_PER_USER = RateRule("password_change_user", 5, HOUR)


def _auth_out(user: User, tokens: object) -> AuthOut:
    return AuthOut.model_validate({"user": UserOut.model_validate(user), "tokens": tokens})


@router.post("/auth/guest", status_code=status.HTTP_201_CREATED, response_model=AuthOut)
def create_guest(
    request: Request,
    body: GuestIn | None = None,
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
    settings: Settings = Depends(get_settings_dep),
) -> AuthOut:
    rate_limit(request, GUEST_PER_IP, client_ip(request), now)
    user, tokens = service.create_guest(
        db, timezone=body.timezone if body else None, now=now, settings=settings
    )
    return _auth_out(user, tokens)


@router.post("/auth/register", status_code=status.HTTP_201_CREATED, response_model=AuthOut)
def register(
    request: Request,
    body: RegisterIn,
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
    settings: Settings = Depends(get_settings_dep),
) -> AuthOut:
    rate_limit(request, REGISTER_PER_IP, client_ip(request), now)
    user, tokens = service.register(db, body, now=now, settings=settings)
    return _auth_out(user, tokens)


@router.post("/auth/upgrade", response_model=AuthOut)
def upgrade(
    request: Request,
    body: UpgradeIn,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
    settings: Settings = Depends(get_settings_dep),
) -> AuthOut:
    rate_limit(request, REGISTER_PER_IP, client_ip(request), now)
    user, tokens = service.upgrade_guest(db, current.id, body, now=now, settings=settings)
    return _auth_out(user, tokens)


@router.post("/auth/login", response_model=AuthOut)
def login(
    request: Request,
    body: LoginIn,
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
    settings: Settings = Depends(get_settings_dep),
) -> AuthOut:
    ip = client_ip(request)
    rate_limit(request, LOGIN_PER_IP, ip, now)
    rate_limit(request, LOGIN_PER_ACCOUNT_MINUTE, f"{ip}|{body.email}", now)
    rate_limit(request, LOGIN_PER_ACCOUNT_HOUR, f"{ip}|{body.email}", now)
    user, tokens = service.login(
        db, email=body.email, password=body.password, now=now, settings=settings
    )
    return _auth_out(user, tokens)


@router.post("/auth/refresh", response_model=TokensResponse)
def refresh(
    body: RefreshIn,
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
    settings: Settings = Depends(get_settings_dep),
) -> TokensResponse:
    tokens = service.refresh(db, raw_token=body.refresh_token, now=now, settings=settings)
    return TokensResponse(tokens=tokens)


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    body: LogoutIn,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
) -> Response:
    service.logout(db, user_id=current.id, raw_token=body.refresh_token, now=now)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/me/password", response_model=TokensResponse)
def change_password(
    request: Request,
    body: PasswordChangeIn,
    current: User = Depends(require_full_account),
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
    settings: Settings = Depends(get_settings_dep),
) -> TokensResponse:
    rate_limit(request, PASSWORD_CHANGE_PER_USER, str(current.id), now)
    tokens = service.change_password(
        db,
        current,
        current_password=body.current_password,
        new_password=body.new_password,
        now=now,
        settings=settings,
    )
    return TokensResponse(tokens=tokens)
