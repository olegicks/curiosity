import uuid
from datetime import timedelta

import jwt
import pytest

from app.auth.passwords import password_problem
from app.core.errors import RateLimitedError
from app.core.ratelimit import FixedWindowRateLimiter, RateRule
from app.core.security import (
    AccessClaims,
    InvalidTokenError,
    create_access_token,
    decode_access_token,
    hash_opaque_token,
    hash_password,
    new_opaque_token,
    verify_password,
)
from app.users.schemas import normalize_display_name
from tests.conftest import TEST_JWT_SECRET, TEST_NOW, make_settings

SETTINGS = make_settings()
CLAIMS = AccessClaims(user_id=uuid.uuid4(), token_version=3, is_guest=True)

# --- passwords ---------------------------------------------------------------------------


def test_password_hash_roundtrip() -> None:
    hashed = hash_password("correct horse battery")
    assert hashed.startswith("$argon2id$")
    assert verify_password(hashed, "correct horse battery")
    assert not verify_password(hashed, "wrong horse battery")
    assert not verify_password("not-a-hash", "anything")


@pytest.mark.parametrize(
    ("password", "email", "problem"),
    [
        ("short", None, "too_short"),
        ("x" * 129, None, "too_long"),
        ("aaaaaaaaaaaa", None, "too_common"),
        ("Password123", None, "too_common"),  # case-insensitive list match
        ("maya@example.com", "Maya@Example.com", "same_as_email"),
        ("a sensible passphrase", "maya@example.com", None),
    ],
)
def test_password_policy(password: str, email: str | None, problem: str | None) -> None:
    assert password_problem(password, email) == problem


# --- access tokens -----------------------------------------------------------------------


def test_access_token_roundtrip() -> None:
    token, ttl = create_access_token(CLAIMS, now=TEST_NOW, settings=SETTINGS)
    assert ttl == 900
    assert decode_access_token(token, now=TEST_NOW, settings=SETTINGS) == CLAIMS


def test_access_token_expires_with_injected_clock() -> None:
    token, _ = create_access_token(CLAIMS, now=TEST_NOW, settings=SETTINGS)
    decode_access_token(token, now=TEST_NOW + timedelta(seconds=899), settings=SETTINGS)
    with pytest.raises(InvalidTokenError):
        decode_access_token(token, now=TEST_NOW + timedelta(seconds=900), settings=SETTINGS)


def test_access_token_rejects_other_secret_and_audience() -> None:
    token, _ = create_access_token(CLAIMS, now=TEST_NOW, settings=SETTINGS)
    other = make_settings(jwt_secret="another-secret-another-secret-another-1")
    with pytest.raises(InvalidTokenError):
        decode_access_token(token, now=TEST_NOW, settings=other)

    payload = jwt.decode(token, options={"verify_signature": False})
    payload["aud"] = "someone-else"
    forged = jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")
    with pytest.raises(InvalidTokenError):
        decode_access_token(forged, now=TEST_NOW, settings=SETTINGS)


def test_access_token_rejects_alg_none() -> None:
    payload = jwt.decode(
        create_access_token(CLAIMS, now=TEST_NOW, settings=SETTINGS)[0],
        options={"verify_signature": False},
    )
    unsigned = jwt.encode(payload, key=None, algorithm="none")
    with pytest.raises(InvalidTokenError):
        decode_access_token(unsigned, now=TEST_NOW, settings=SETTINGS)


def test_opaque_tokens_are_random_and_hashed() -> None:
    raw, digest = new_opaque_token()
    assert len(raw) >= 43
    assert digest == hash_opaque_token(raw)
    assert new_opaque_token()[0] != raw


def test_settings_reject_short_jwt_secret() -> None:
    with pytest.raises(ValueError, match="32 bytes"):
        make_settings(jwt_secret="too-short")


# --- rate limiter --------------------------------------------------------------------------


def test_fixed_window_limits_and_resets() -> None:
    limiter = FixedWindowRateLimiter()
    rule = RateRule("t", 2, 60)
    start = TEST_NOW  # 12:00:00, aligned to the window
    limiter.hit(rule, "k", start)
    limiter.hit(rule, "k", start + timedelta(seconds=10))
    limiter.hit(rule, "other", start)  # separate key
    with pytest.raises(RateLimitedError) as excinfo:
        limiter.hit(rule, "k", start + timedelta(seconds=20))
    assert excinfo.value.headers == {"Retry-After": "40"}
    limiter.hit(rule, "k", start + timedelta(seconds=60))  # next window


# --- display names -------------------------------------------------------------------------


def test_display_name_normalization() -> None:
    assert normalize_display_name("  Maya  ") == "Maya"
    assert normalize_display_name(None) is None
    for bad in ["   ", "x" * 41, "Ma\x00ya", "line\nbreak"]:
        with pytest.raises(ValueError, match="display name"):
            normalize_display_name(bad)
