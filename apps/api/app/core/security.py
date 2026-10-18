"""Password hashing, access tokens (JWT) and opaque refresh tokens (docs/spec/09 §9.1)."""

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import lru_cache

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.config import Settings

JWT_ALGORITHM = "HS256"
JWT_ISSUER = "curiosity-api"
JWT_AUDIENCE = "curiosity-app"

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


@lru_cache(maxsize=1)
def _dummy_hash() -> str:
    return _hasher.hash(secrets.token_urlsafe(16))


def burn_password_check(password: str) -> None:
    """Spend the same time as a real verification (unknown email on login)."""
    verify_password(_dummy_hash(), password)


# --- access tokens -----------------------------------------------------------------------


@dataclass(frozen=True)
class AccessClaims:
    user_id: uuid.UUID
    token_version: int
    is_guest: bool


class InvalidTokenError(Exception):
    pass


def create_access_token(
    claims: AccessClaims, *, now: datetime, settings: Settings
) -> tuple[str, int]:
    """Return (token, lifetime in seconds)."""
    ttl = settings.access_token_ttl_seconds
    payload = {
        "sub": str(claims.user_id),
        "ver": claims.token_version,
        "guest": claims.is_guest,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=ttl)).timestamp()),
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
    }
    token = jwt.encode(payload, settings.jwt_secret.get_secret_value(), algorithm=JWT_ALGORITHM)
    return token, ttl


def decode_access_token(token: str, *, now: datetime, settings: Settings) -> AccessClaims:
    """Verify signature, issuer, audience and expiry (against the injected clock)."""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[JWT_ALGORITHM],
            audience=JWT_AUDIENCE,
            issuer=JWT_ISSUER,
            # Time checks use the injected clock below, not PyJWT's wall clock.
            options={
                "verify_exp": False,
                "verify_iat": False,
                "verify_nbf": False,
                "require": ["sub", "ver", "exp", "iss", "aud"],
            },
        )
        if int(payload["exp"]) <= int(now.timestamp()):
            raise InvalidTokenError("expired")
        return AccessClaims(
            user_id=uuid.UUID(str(payload["sub"])),
            token_version=int(payload["ver"]),
            is_guest=bool(payload.get("guest", False)),
        )
    except (jwt.PyJWTError, ValueError, TypeError, KeyError) as exc:
        raise InvalidTokenError(str(exc)) from exc


# --- refresh / single-use tokens -----------------------------------------------------------


def new_opaque_token() -> tuple[str, bytes]:
    """Return (raw token for the client, SHA-256 digest to store)."""
    raw = secrets.token_urlsafe(32)  # 256 bits
    return raw, hash_opaque_token(raw)


def hash_opaque_token(raw: str) -> bytes:
    return hashlib.sha256(raw.encode()).digest()
