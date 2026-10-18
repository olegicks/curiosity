"""Auth and /me endpoints against PostgreSQL (docs/spec/11 §11.3 T-AUTH-*)."""

import uuid
from collections.abc import Callable
from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.models import RefreshToken, User
from app.core.clock import FixedClock
from app.users.models import UserPreferences

pytestmark = pytest.mark.db

PASSWORD = "a sensible passphrase"


def bearer(tokens: dict[str, Any]) -> dict[str, str]:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def new_guest(client: TestClient, timezone: str | None = "Europe/Kyiv") -> dict[str, Any]:
    response = client.post("/v1/auth/guest", json={"timezone": timezone})
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


def new_user(client: TestClient, email: str = "maya@example.com") -> dict[str, Any]:
    response = client.post(
        "/v1/auth/register", json={"email": email, "password": PASSWORD, "display_name": "Maya"}
    )
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


def error_code(response: Any) -> str:
    return str(response.json()["error"]["code"])


# --- guest ---------------------------------------------------------------------------------


def test_guest_creation_returns_tokens_and_profile(db_client: TestClient) -> None:
    body = new_guest(db_client)
    assert body["user"]["is_guest"] is True
    assert body["user"]["email"] is None
    assert body["tokens"]["token_type"] == "Bearer"
    assert body["tokens"]["access_expires_in"] == 900

    me = db_client.get("/v1/me", headers=bearer(body["tokens"]))
    assert me.status_code == 200
    assert me.json()["user"]["id"] == body["user"]["id"]
    assert me.json()["preferences"] == {
        "timezone": "Europe/Kyiv",
        "daily_xp_goal": 20,
        "interest_topics": [],
        "onboarding_completed": False,
    }


@pytest.mark.parametrize("payload", [None, {}, {"timezone": "Mars/Olympus"}])
def test_guest_timezone_falls_back_to_utc(db_client: TestClient, payload: Any) -> None:
    response = db_client.post("/v1/auth/guest", json=payload)
    assert response.status_code == 201
    me = db_client.get("/v1/me", headers=bearer(response.json()["tokens"]))
    assert me.json()["preferences"]["timezone"] == "UTC"


# --- register --------------------------------------------------------------------------------


def test_register_normalizes_email_and_stores_only_hashes(
    db_client: TestClient, db_session: Session
) -> None:
    body = new_user(db_client, email="  Maya@Example.COM ")
    assert body["user"]["email"] == "maya@example.com"
    assert body["user"]["display_name"] == "Maya"

    user = db_session.get(User, uuid.UUID(body["user"]["id"]))
    assert user is not None
    assert user.password_hash is not None
    assert user.password_hash.startswith("$argon2id$")
    token_row = db_session.scalars(
        select(RefreshToken).where(RefreshToken.user_id == user.id)
    ).one()
    assert body["tokens"]["refresh_token"].encode() not in token_row.token_hash


def test_register_rejects_duplicate_email_case_insensitively(db_client: TestClient) -> None:
    new_user(db_client, email="maya@example.com")
    response = db_client.post(
        "/v1/auth/register", json={"email": "MAYA@example.com", "password": PASSWORD}
    )
    assert response.status_code == 409
    assert error_code(response) == "EMAIL_TAKEN"


@pytest.mark.parametrize(
    ("password", "issue"),
    [("short", "too_short"), ("password123", "too_common"), ("dan@example.com", "same_as_email")],
)
def test_register_rejects_weak_passwords(db_client: TestClient, password: str, issue: str) -> None:
    response = db_client.post(
        "/v1/auth/register", json={"email": "dan@example.com", "password": password}
    )
    assert response.status_code == 422
    assert error_code(response) == "WEAK_PASSWORD"
    assert response.json()["error"]["details"] == [{"field": "password", "issue": issue}]


def test_register_validates_email_and_unknown_fields(db_client: TestClient) -> None:
    bad_email = db_client.post("/v1/auth/register", json={"email": "nope", "password": PASSWORD})
    assert bad_email.status_code == 422
    extra = db_client.post(
        "/v1/auth/register",
        json={"email": "a@example.com", "password": PASSWORD, "is_internal": True},
    )
    assert extra.status_code == 422
    assert extra.json()["error"]["details"] == [
        {"field": "is_internal", "issue": "extra_forbidden"}
    ]


# --- upgrade -----------------------------------------------------------------------------------


def test_upgrade_keeps_user_id_and_invalidates_guest_tokens(db_client: TestClient) -> None:
    guest = new_guest(db_client)
    response = db_client.post(
        "/v1/auth/upgrade",
        headers=bearer(guest["tokens"]),
        json={"email": "ruth@example.com", "password": PASSWORD, "display_name": " Ruth "},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["user"] == {
        **guest["user"],
        "is_guest": False,
        "email": "ruth@example.com",
        "display_name": "Ruth",
    }

    assert db_client.get("/v1/me", headers=bearer(guest["tokens"])).status_code == 401
    old_refresh = db_client.post(
        "/v1/auth/refresh", json={"refresh_token": guest["tokens"]["refresh_token"]}
    )
    assert old_refresh.status_code == 401
    assert db_client.get("/v1/me", headers=bearer(body["tokens"])).status_code == 200

    login = db_client.post(
        "/v1/auth/login", json={"email": "ruth@example.com", "password": PASSWORD}
    )
    assert login.status_code == 200
    assert login.json()["user"]["id"] == guest["user"]["id"]


def test_upgrade_twice_or_from_full_account_conflicts(db_client: TestClient) -> None:
    guest = new_guest(db_client)
    first = db_client.post(
        "/v1/auth/upgrade",
        headers=bearer(guest["tokens"]),
        json={"email": "ruth@example.com", "password": PASSWORD},
    )
    again = db_client.post(
        "/v1/auth/upgrade",
        headers=bearer(first.json()["tokens"]),
        json={"email": "ruth2@example.com", "password": PASSWORD},
    )
    assert again.status_code == 409
    assert error_code(again) == "ALREADY_FULL_ACCOUNT"


def test_upgrade_with_taken_email_conflicts(db_client: TestClient) -> None:
    new_user(db_client, email="maya@example.com")
    guest = new_guest(db_client)
    response = db_client.post(
        "/v1/auth/upgrade",
        headers=bearer(guest["tokens"]),
        json={"email": "maya@example.com", "password": PASSWORD},
    )
    assert response.status_code == 409
    assert error_code(response) == "EMAIL_TAKEN"


# --- login -------------------------------------------------------------------------------------


def test_login_failure_is_identical_for_unknown_email_and_wrong_password(
    db_client: TestClient,
) -> None:
    new_user(db_client)
    wrong = db_client.post(
        "/v1/auth/login", json={"email": "maya@example.com", "password": "not the password"}
    )
    unknown = db_client.post(
        "/v1/auth/login", json={"email": "nobody@example.com", "password": "not the password"}
    )
    assert wrong.status_code == unknown.status_code == 401

    def strip(response: Any) -> dict[str, Any]:
        return {k: v for k, v in response.json()["error"].items() if k != "request_id"}

    assert strip(wrong) == strip(unknown)
    assert strip(wrong)["code"] == "INVALID_CREDENTIALS"


def test_login_is_case_insensitive_on_email(db_client: TestClient) -> None:
    new_user(db_client)
    response = db_client.post(
        "/v1/auth/login", json={"email": "MAYA@EXAMPLE.COM", "password": PASSWORD}
    )
    assert response.status_code == 200


# --- access tokens -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "headers",
    [{}, {"Authorization": "Bearer not-a-jwt"}, {"Authorization": "Basic dXNlcjpwYXNz"}],
)
def test_protected_endpoint_requires_valid_bearer(
    db_client: TestClient, headers: dict[str, str]
) -> None:
    response = db_client.get("/v1/me", headers=headers)
    assert response.status_code == 401
    assert error_code(response) == "UNAUTHENTICATED"


def test_access_token_expires(db_client: TestClient, clock: FixedClock) -> None:
    tokens = new_guest(db_client)["tokens"]
    clock.advance(timedelta(minutes=15))
    assert db_client.get("/v1/me", headers=bearer(tokens)).status_code == 401


def test_last_seen_updates_at_most_hourly(
    db_client: TestClient, db_session: Session, clock: FixedClock
) -> None:
    guest = new_guest(db_client)
    user_id = uuid.UUID(guest["user"]["id"])
    created = db_session.get(User, user_id)
    assert created is not None
    first_seen = created.last_seen_at

    clock.advance(timedelta(minutes=10))
    db_client.get("/v1/me", headers=bearer(guest["tokens"]))
    assert db_session.get(User, user_id).last_seen_at == first_seen  # type: ignore[union-attr]

    clock.advance(timedelta(hours=1))
    login = db_client.post(
        "/v1/auth/refresh", json={"refresh_token": guest["tokens"]["refresh_token"]}
    )
    db_client.get("/v1/me", headers=bearer(login.json()["tokens"]))
    assert db_session.get(User, user_id).last_seen_at == clock.now()  # type: ignore[union-attr]


# --- refresh rotation ----------------------------------------------------------------------------


def test_refresh_rotates_tokens(db_client: TestClient) -> None:
    tokens = new_guest(db_client)["tokens"]
    response = db_client.post("/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert response.status_code == 200
    new_tokens = response.json()["tokens"]
    assert new_tokens["refresh_token"] != tokens["refresh_token"]
    assert db_client.get("/v1/me", headers=bearer(new_tokens)).status_code == 200


def test_refresh_reuse_after_grace_revokes_family(db_client: TestClient, clock: FixedClock) -> None:
    tokens = new_guest(db_client)["tokens"]
    successor = db_client.post(
        "/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    ).json()["tokens"]

    clock.advance(timedelta(seconds=11))
    reuse = db_client.post("/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert reuse.status_code == 401
    assert error_code(reuse) == "REFRESH_TOKEN_REUSED"

    after = db_client.post("/v1/auth/refresh", json={"refresh_token": successor["refresh_token"]})
    assert after.status_code == 401
    assert error_code(after) == "INVALID_REFRESH_TOKEN"


def test_refresh_reuse_within_grace_is_tolerated(db_client: TestClient, clock: FixedClock) -> None:
    tokens = new_guest(db_client)["tokens"]
    first = db_client.post("/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    clock.advance(timedelta(seconds=5))
    second = db_client.post("/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert first.status_code == second.status_code == 200
    for result in (first, second):
        refreshed = db_client.post(
            "/v1/auth/refresh", json={"refresh_token": result.json()["tokens"]["refresh_token"]}
        )
        assert refreshed.status_code == 200


def test_refresh_token_expires(db_client: TestClient, clock: FixedClock) -> None:
    tokens = new_guest(db_client)["tokens"]
    clock.advance(timedelta(days=30))
    response = db_client.post("/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert response.status_code == 401
    assert error_code(response) == "INVALID_REFRESH_TOKEN"


def test_refresh_rejects_unknown_token(db_client: TestClient) -> None:
    response = db_client.post("/v1/auth/refresh", json={"refresh_token": "made-up"})
    assert response.status_code == 401


# --- logout ---------------------------------------------------------------------------------------


def test_logout_revokes_family_and_is_idempotent(db_client: TestClient) -> None:
    tokens = new_guest(db_client)["tokens"]
    for _ in range(2):
        response = db_client.post(
            "/v1/auth/logout",
            headers=bearer(tokens),
            json={"refresh_token": tokens["refresh_token"]},
        )
        assert response.status_code == 204
    refresh = db_client.post("/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert refresh.status_code == 401


def test_logout_cannot_revoke_another_users_token(db_client: TestClient) -> None:
    alice = new_guest(db_client)["tokens"]
    bob = new_guest(db_client)["tokens"]
    response = db_client.post(
        "/v1/auth/logout", headers=bearer(alice), json={"refresh_token": bob["refresh_token"]}
    )
    assert response.status_code == 204
    refresh = db_client.post("/v1/auth/refresh", json={"refresh_token": bob["refresh_token"]})
    assert refresh.status_code == 200


# --- password change ------------------------------------------------------------------------------


def test_password_change_requires_full_account(db_client: TestClient) -> None:
    guest = new_guest(db_client)
    response = db_client.post(
        "/v1/me/password",
        headers=bearer(guest["tokens"]),
        json={"current_password": "x", "new_password": "another good passphrase"},
    )
    assert response.status_code == 403
    assert error_code(response) == "FULL_ACCOUNT_REQUIRED"


def test_password_change_rotates_everything(db_client: TestClient) -> None:
    user = new_user(db_client)
    wrong = db_client.post(
        "/v1/me/password",
        headers=bearer(user["tokens"]),
        json={"current_password": "nope", "new_password": "another good passphrase"},
    )
    assert wrong.status_code == 401

    response = db_client.post(
        "/v1/me/password",
        headers=bearer(user["tokens"]),
        json={"current_password": PASSWORD, "new_password": "another good passphrase"},
    )
    assert response.status_code == 200
    assert db_client.get("/v1/me", headers=bearer(user["tokens"])).status_code == 401
    old_refresh = db_client.post(
        "/v1/auth/refresh", json={"refresh_token": user["tokens"]["refresh_token"]}
    )
    assert old_refresh.status_code == 401
    assert db_client.get("/v1/me", headers=bearer(response.json()["tokens"])).status_code == 200
    login = db_client.post(
        "/v1/auth/login",
        json={"email": "maya@example.com", "password": "another good passphrase"},
    )
    assert login.status_code == 200


# --- /me and preferences --------------------------------------------------------------------------


def test_patch_me_display_name(db_client: TestClient) -> None:
    headers = bearer(new_guest(db_client)["tokens"])
    response = db_client.patch("/v1/me", headers=headers, json={"display_name": "  Daniel "})
    assert response.status_code == 200
    assert response.json()["user"]["display_name"] == "Daniel"

    bad = db_client.patch("/v1/me", headers=headers, json={"display_name": "Dan\u0007iel"})
    assert bad.status_code == 422

    cleared = db_client.patch("/v1/me", headers=headers, json={"display_name": None})
    assert cleared.json()["user"]["display_name"] is None


def test_patch_preferences(db_client: TestClient, clock: FixedClock) -> None:
    headers = bearer(new_guest(db_client)["tokens"])
    response = db_client.patch(
        "/v1/me/preferences",
        headers=headers,
        json={"timezone": "America/Los_Angeles", "daily_xp_goal": 40, "onboarding_completed": True},
    )
    assert response.status_code == 200
    assert response.json() == {
        "timezone": "America/Los_Angeles",
        "daily_xp_goal": 40,
        "interest_topics": [],
        "onboarding_completed": True,
    }
    assert db_client.get("/v1/me/preferences", headers=headers).json() == response.json()


@pytest.mark.parametrize(
    ("payload", "code"),
    [
        ({"timezone": "Mars/Olympus"}, "INVALID_TIMEZONE"),
        ({"daily_xp_goal": 30}, "VALIDATION_ERROR"),
        ({"interest_topics": ["decisions"]}, "UNKNOWN_TOPIC"),
        ({"interest_topics": ["a", "b", "c", "d"]}, "VALIDATION_ERROR"),
        ({"onboarding_completed": False}, "VALIDATION_ERROR"),
    ],
)
def test_patch_preferences_validation(
    db_client: TestClient, payload: dict[str, Any], code: str
) -> None:
    headers = bearer(new_guest(db_client)["tokens"])
    response = db_client.patch("/v1/me/preferences", headers=headers, json=payload)
    assert response.status_code == 422
    assert error_code(response) == code


def test_users_only_see_their_own_profile(db_client: TestClient) -> None:
    alice = new_user(db_client, email="alice@example.com")
    bob = new_user(db_client, email="bob@example.com")
    assert (
        db_client.get("/v1/me", headers=bearer(alice["tokens"])).json()["user"]["id"]
        == (alice["user"]["id"])
    )
    db_client.patch("/v1/me", headers=bearer(bob["tokens"]), json={"display_name": "Bob"})
    assert (
        db_client.get("/v1/me", headers=bearer(alice["tokens"])).json()["user"]["display_name"]
        == "Maya"
    )


# --- account deletion -----------------------------------------------------------------------------


def _owned_rows(db_session: Session, user_id: uuid.UUID) -> int:
    counts = [
        db_session.scalar(select(func.count()).select_from(User).where(User.id == user_id)),
        db_session.scalar(
            select(func.count()).select_from(RefreshToken).where(RefreshToken.user_id == user_id)
        ),
        db_session.scalar(
            select(func.count())
            .select_from(UserPreferences)
            .where(UserPreferences.user_id == user_id)
        ),
    ]
    return sum(c or 0 for c in counts)


def test_guest_deletion_requires_confirmation_and_removes_rows(
    db_client: TestClient, db_session: Session
) -> None:
    guest = new_guest(db_client)
    user_id = uuid.UUID(guest["user"]["id"])
    headers = bearer(guest["tokens"])

    missing = db_client.request("DELETE", "/v1/me", headers=headers, json={})
    assert missing.status_code == 422
    assert error_code(missing) == "CONFIRMATION_REQUIRED"

    response = db_client.request("DELETE", "/v1/me", headers=headers, json={"confirm": "DELETE"})
    assert response.status_code == 204
    db_session.expire_all()
    assert _owned_rows(db_session, user_id) == 0
    assert db_client.get("/v1/me", headers=headers).status_code == 401
    refresh = db_client.post(
        "/v1/auth/refresh", json={"refresh_token": guest["tokens"]["refresh_token"]}
    )
    assert refresh.status_code == 401


def test_full_account_deletion_requires_password(
    db_client: TestClient, db_session: Session
) -> None:
    user = new_user(db_client)
    headers = bearer(user["tokens"])
    wrong = db_client.request("DELETE", "/v1/me", headers=headers, json={"password": "nope"})
    assert wrong.status_code == 401
    assert error_code(wrong) == "INVALID_CREDENTIALS"

    response = db_client.request("DELETE", "/v1/me", headers=headers, json={"password": PASSWORD})
    assert response.status_code == 204
    db_session.expire_all()
    assert _owned_rows(db_session, uuid.UUID(user["user"]["id"])) == 0
    login = db_client.post(
        "/v1/auth/login", json={"email": "maya@example.com", "password": PASSWORD}
    )
    assert login.status_code == 401


# --- rate limiting --------------------------------------------------------------------------------


def test_register_rate_limited_per_ip(make_db_client: Callable[..., TestClient]) -> None:
    client = make_db_client(rate_limit_enabled=True)
    statuses = [
        client.post(
            "/v1/auth/register", json={"email": f"u{i}@example.com", "password": PASSWORD}
        ).status_code
        for i in range(6)
    ]
    assert statuses == [201] * 5 + [429]


def test_login_rate_limited_per_account(make_db_client: Callable[..., TestClient]) -> None:
    client = make_db_client(rate_limit_enabled=True)
    new_user(client)
    responses = [
        client.post("/v1/auth/login", json={"email": "maya@example.com", "password": "wrong one"})
        for _ in range(6)
    ]
    assert [r.status_code for r in responses] == [401] * 5 + [429]
    assert error_code(responses[-1]) == "RATE_LIMITED"
    assert int(responses[-1].headers["Retry-After"]) > 0
