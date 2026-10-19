"""Account creation, sign-in and token lifecycle (docs/spec/05 §5.2, 09 §9.1).

Every public function owns its transaction and commits before returning.
"""

import uuid
from datetime import datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.analytics.emit import emit
from app.auth.errors import (
    AlreadyFullAccountError,
    EmailTakenError,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
    RefreshTokenReusedError,
    WeakPasswordError,
)
from app.auth.models import RefreshToken, User
from app.auth.passwords import password_problem
from app.auth.schemas import RegisterIn, TokensOut, UpgradeIn
from app.config import Settings
from app.core.ids import uuid7
from app.core.security import (
    AccessClaims,
    InvalidTokenError,
    burn_password_check,
    create_access_token,
    decode_access_token,
    hash_opaque_token,
    hash_password,
    new_opaque_token,
    password_needs_rehash,
    verify_password,
)
from app.users.service import create_default_preferences, get_preferences

LAST_SEEN_RESOLUTION = timedelta(hours=1)


def _check_password(password: str, email: str | None, field: str = "password") -> None:
    problem = password_problem(password, email)
    if problem:
        raise WeakPasswordError(problem, field)


def _email_taken(db: Session, email: str) -> bool:
    return db.scalar(select(User.id).where(User.email == email)) is not None


def _issue_tokens(
    db: Session,
    user: User,
    *,
    now: datetime,
    settings: Settings,
    family_id: uuid.UUID | None = None,
) -> TokensOut:
    """Create a refresh token row (caller commits) and a matching access token."""
    raw, digest = new_opaque_token()
    db.add(
        RefreshToken(
            user_id=user.id,
            family_id=family_id or uuid7(),
            token_hash=digest,
            expires_at=now + timedelta(days=settings.refresh_token_ttl_days),
        )
    )
    access, expires_in = create_access_token(
        AccessClaims(user_id=user.id, token_version=user.token_version, is_guest=user.is_guest),
        now=now,
        settings=settings,
    )
    return TokensOut(access_token=access, access_expires_in=expires_in, refresh_token=raw)


def _revoke_all_refresh_tokens(db: Session, user_id: uuid.UUID, now: datetime) -> None:
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=now)
    )


def _commit_or_email_taken(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as exc:  # concurrent registration with the same email
        db.rollback()
        if "uq_users_email" in str(exc.orig):
            raise EmailTakenError from None
        raise


def create_guest(
    db: Session, *, timezone: str | None, now: datetime, settings: Settings
) -> tuple[User, TokensOut]:
    user = User(id=uuid7(), is_guest=True, token_version=0, last_seen_at=now)
    db.add(user)
    db.flush()
    create_default_preferences(db, user.id, timezone)
    tokens = _issue_tokens(db, user, now=now, settings=settings)
    emit(db, "guest_created", user_id=user.id, now=now, timezone=timezone)
    db.commit()
    return user, tokens


def register(
    db: Session, data: RegisterIn, *, now: datetime, settings: Settings
) -> tuple[User, TokensOut]:
    _check_password(data.password, data.email)
    if _email_taken(db, data.email):
        raise EmailTakenError
    user = User(
        id=uuid7(),
        email=data.email,
        password_hash=hash_password(data.password),
        display_name=data.display_name,
        is_guest=False,
        token_version=0,
        last_seen_at=now,
    )
    db.add(user)
    try:
        db.flush()  # user row must exist before rows that reference it
    except IntegrityError:
        db.rollback()
        raise EmailTakenError from None
    create_default_preferences(db, user.id, data.timezone)
    tokens = _issue_tokens(db, user, now=now, settings=settings)
    _commit_or_email_taken(db)
    return user, tokens


def upgrade_guest(
    db: Session, user_id: uuid.UUID, data: UpgradeIn, *, now: datetime, settings: Settings
) -> tuple[User, TokensOut]:
    """Attach credentials to the current guest; same user id, all progress kept."""
    user = db.scalar(select(User).where(User.id == user_id).with_for_update())
    if user is None:
        raise InvalidRefreshTokenError
    if not user.is_guest:
        raise AlreadyFullAccountError
    _check_password(data.password, data.email)
    if _email_taken(db, data.email):
        raise EmailTakenError
    user.email = data.email
    user.password_hash = hash_password(data.password)
    if data.display_name is not None:
        user.display_name = data.display_name
    user.is_guest = False
    user.upgraded_at = now
    user.token_version += 1  # guest access tokens stop working
    _revoke_all_refresh_tokens(db, user.id, now)
    tokens = _issue_tokens(db, user, now=now, settings=settings)
    emit(
        db,
        "account_upgraded",
        user_id=user.id,
        now=now,
        timezone=get_preferences(db, user.id).timezone,
    )
    _commit_or_email_taken(db)
    return user, tokens


def login(
    db: Session, *, email: str, password: str, now: datetime, settings: Settings
) -> tuple[User, TokensOut]:
    user = db.scalar(select(User).where(User.email == email))
    if user is None or user.password_hash is None:
        burn_password_check(password)
        raise InvalidCredentialsError
    if not verify_password(user.password_hash, password):
        raise InvalidCredentialsError
    if password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    user.last_seen_at = now
    tokens = _issue_tokens(db, user, now=now, settings=settings)
    db.commit()
    return user, tokens


def refresh(db: Session, *, raw_token: str, now: datetime, settings: Settings) -> TokensOut:
    """Rotate a refresh token. Reuse of a rotated token revokes its whole family.

    Within the grace window a reused token gets a fresh sibling in the same family
    (parallel refreshes from the app), because successors are stored only as hashes.
    """
    token = db.scalar(
        select(RefreshToken)
        .where(RefreshToken.token_hash == hash_opaque_token(raw_token))
        .with_for_update()
    )
    if token is None or token.revoked_at is not None or token.expires_at <= now:
        raise InvalidRefreshTokenError
    if token.rotated_at is not None:
        grace = timedelta(seconds=settings.refresh_reuse_grace_seconds)
        if now - token.rotated_at > grace:
            db.execute(
                update(RefreshToken)
                .where(RefreshToken.family_id == token.family_id, RefreshToken.revoked_at.is_(None))
                .values(revoked_at=now)
            )
            db.commit()
            raise RefreshTokenReusedError
    else:
        token.rotated_at = now
    user = db.get(User, token.user_id)
    if user is None:
        raise InvalidRefreshTokenError
    tokens = _issue_tokens(db, user, now=now, settings=settings, family_id=token.family_id)
    db.commit()
    return tokens


def logout(db: Session, *, user_id: uuid.UUID, raw_token: str, now: datetime) -> None:
    """Revoke the token's family. Unknown or foreign tokens are ignored (idempotent)."""
    token = db.scalar(
        select(RefreshToken).where(
            RefreshToken.token_hash == hash_opaque_token(raw_token),
            RefreshToken.user_id == user_id,
        )
    )
    if token is not None:
        db.execute(
            update(RefreshToken)
            .where(RefreshToken.family_id == token.family_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=now)
        )
    db.commit()


def change_password(
    db: Session,
    user: User,
    *,
    current_password: str,
    new_password: str,
    now: datetime,
    settings: Settings,
) -> TokensOut:
    if not user.password_hash or not verify_password(user.password_hash, current_password):
        raise InvalidCredentialsError("Current password is incorrect.")
    _check_password(new_password, user.email, field="new_password")
    user.password_hash = hash_password(new_password)
    user.token_version += 1
    _revoke_all_refresh_tokens(db, user.id, now)
    tokens = _issue_tokens(db, user, now=now, settings=settings)
    db.commit()
    return tokens


def authenticate(db: Session, *, access_token: str, now: datetime, settings: Settings) -> User:
    """Resolve the user for a bearer token; raises InvalidTokenError when unusable."""
    claims = decode_access_token(access_token, now=now, settings=settings)
    user = db.get(User, claims.user_id)
    if user is None or user.token_version != claims.token_version:
        raise InvalidTokenError("revoked")
    if user.last_seen_at is None or now - user.last_seen_at >= LAST_SEEN_RESOLUTION:
        user.last_seen_at = now
        db.commit()
    return user
