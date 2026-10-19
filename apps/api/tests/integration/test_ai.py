"""AI explanations: cache, limits, budget, failures, feedback (docs/spec/11 T-AI-*)."""

import uuid
from collections.abc import Callable
from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.models import AiExplanation, AiExplanationFeedback, AiRequest
from app.ai.provider import FakeProvider, GenerationResult, ProviderError, ProviderTimeoutError
from app.core.clock import FixedClock
from tests.conftest import Importer
from tests.content_factory import standard_lessons

pytestmark = pytest.mark.db

PRICED = {
    "ai_price_input_per_mtok_micros": 4_000_000,
    "ai_price_output_per_mtok_micros": 20_000_000,
}


class Env:
    def __init__(self, make_client: Callable[..., TestClient], **settings: Any) -> None:
        self.provider = FakeProvider()
        self.client = make_client(ai_provider=self.provider, **settings)
        self.version = ""

    def guest(self) -> dict[str, str]:
        tokens = self.client.post("/v1/auth/guest", json={}).json()["tokens"]
        return {"Authorization": f"Bearer {tokens['access_token']}"}

    def explain(
        self, auth: dict[str, str], mode: str = "simpler", slug: str = "anchoring", **extra: Any
    ) -> Any:
        if not self.version:
            self.version = self.client.get(f"/v1/lessons/{slug}", headers=auth).json()["content"][
                "lesson_version_id"
            ]
        body = {"mode": mode, "lesson_version_id": extra.pop("version", self.version), **extra}
        return self.client.post(f"/v1/lessons/{slug}/explanations", headers=auth, json=body)


@pytest.fixture
def make_env(make_db_client: Callable[..., TestClient], run_import: Importer) -> Callable[..., Env]:
    run_import(standard_lessons())
    return lambda **settings: Env(make_db_client, **settings)


def outcomes(db: Session) -> list[str]:
    return list(db.scalars(select(AiRequest.outcome).order_by(AiRequest.created_at, AiRequest.id)))


# --- generation and cache -----------------------------------------------------------------------


def test_first_request_generates_and_logs_cost(
    make_env: Callable[..., Env], db_session: Session
) -> None:
    env = make_env(**PRICED)
    auth = env.guest()
    response = env.explain(auth)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["explanation"]["label"] == "ai_generated"
    assert body["explanation"]["variant"] == 1
    assert body["explanation"]["has_more_variants"] is True
    assert body["usage"] == {"remaining_today": 19, "limit_per_day": 20}
    request = db_session.scalars(select(AiRequest)).one()
    assert (request.outcome, request.input_tokens, request.output_tokens) == (
        "generated",
        1500,
        200,
    )
    assert request.cost_micros == 10_000
    # the prompt holds lesson content only: no questions, no user data
    prompt = env.provider.calls[0].user
    assert "Lesson: Lesson anchoring" in prompt
    assert "question" not in prompt.lower()


def test_cached_explanation_is_shared_across_users(
    make_env: Callable[..., Env], db_session: Session
) -> None:
    env = make_env()
    first = env.explain(env.guest()).json()["explanation"]
    second = env.explain(env.guest()).json()["explanation"]
    assert second["id"] == first["id"]
    assert len(env.provider.calls) == 1
    assert outcomes(db_session) == ["generated", "cache_hit"]


def test_another_version_generates_up_to_the_variant_cap_then_cycles(
    make_env: Callable[..., Env],
) -> None:
    env = make_env(ai_max_variants=3)
    auth = env.guest()
    seen: list[str] = []
    for expected_variant in (1, 2, 3):
        body = env.explain(auth, exclude_ids=seen).json()["explanation"]
        assert body["variant"] == expected_variant
        seen.append(body["id"])
    assert body["has_more_variants"] is False
    cycled = env.explain(auth, exclude_ids=seen).json()["explanation"]
    assert cycled["variant"] == 1
    assert len(env.provider.calls) == 3


def test_modes_are_cached_separately(make_env: Callable[..., Env]) -> None:
    env = make_env()
    auth = env.guest()
    modes = {
        env.explain(auth, mode).json()["explanation"]["mode"]
        for mode in ("simpler", "example", "analogy")
    }
    assert modes == {"simpler", "example", "analogy"}
    assert len(env.provider.calls) == 3


# --- limits and budget ----------------------------------------------------------------------------


def test_burst_limit(make_env: Callable[..., Env], db_session: Session, clock: FixedClock) -> None:
    env = make_env(ai_user_burst_limit=2)
    auth = env.guest()
    assert env.explain(auth).status_code == 200
    assert env.explain(auth).status_code == 200
    limited = env.explain(auth)
    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "AI_RATE_LIMITED"
    assert int(limited.headers["Retry-After"]) == 60
    assert outcomes(db_session)[-1] == "rate_limited"
    clock.advance(timedelta(seconds=61))
    assert env.explain(auth).status_code == 200


def test_daily_limit_counts_cache_hits(make_env: Callable[..., Env], clock: FixedClock) -> None:
    env = make_env(ai_user_daily_limit=2)
    auth = env.guest()
    env.explain(auth)
    clock.advance(timedelta(minutes=5))
    body = env.explain(auth).json()  # cache hit still counts
    assert body["usage"]["remaining_today"] == 0
    clock.advance(timedelta(minutes=5))
    assert env.explain(auth).status_code == 429
    other = env.guest()  # limits are per user
    assert env.explain(other).status_code == 200


def test_global_budget_stops_generation(make_env: Callable[..., Env], db_session: Session) -> None:
    env = make_env(ai_daily_budget_micros=5_000, **PRICED)
    auth = env.guest()
    assert env.explain(auth, "simpler").status_code == 200  # costs 10,000
    blocked = env.explain(auth, "analogy")
    assert blocked.status_code == 503
    assert blocked.json()["error"] == {
        "code": "AI_UNAVAILABLE",
        "message": "Alternative explanations aren't available right now.",
        "details": [{"reason": "budget"}],
        "request_id": blocked.json()["error"]["request_id"],
    }
    assert len(env.provider.calls) == 1
    assert env.explain(auth, "simpler").status_code == 200  # cached content is still served
    assert outcomes(db_session) == ["generated", "budget_exceeded", "cache_hit"]


# --- failures ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("error", "reason", "outcome"),
    [
        (ProviderTimeoutError("slow"), "timeout", "timeout"),
        (ProviderError("down"), "provider", "provider_error"),
    ],
)
def test_provider_failures_do_not_break_learning(
    make_env: Callable[..., Env],
    db_session: Session,
    error: Exception,
    reason: str,
    outcome: str,
) -> None:
    env = make_env()
    env.provider.script.append(error)
    auth = env.guest()
    response = env.explain(auth)
    assert response.status_code == 503
    assert response.json()["error"]["details"] == [{"reason": reason}]
    assert outcomes(db_session) == [outcome]
    # lessons keep working while AI is failing
    started = env.client.post("/v1/lessons/anchoring/attempts", headers=auth)
    assert started.status_code == 201


def test_bad_output_is_retried_once_then_rejected(
    make_env: Callable[..., Env], db_session: Session
) -> None:
    env = make_env(**PRICED)
    bad = GenerationResult("ok", "Too short.", "fake", 1500, 50)
    env.provider.script.extend([bad, bad])
    auth = env.guest()
    response = env.explain(auth)
    assert response.status_code == 503
    assert response.json()["error"]["details"] == [{"reason": "quality"}]
    assert outcomes(db_session) == ["invalid_output", "invalid_output"]
    assert all(r.cost_micros > 0 for r in db_session.scalars(select(AiRequest)))
    assert db_session.scalar(select(func.count()).select_from(AiExplanation)) == 0

    env.provider.script.extend([GenerationResult("cannot_comply", "", "fake", 10, 5)])
    ok = env.explain(auth)  # one refusal-like result, then the default good text
    assert ok.status_code == 200
    assert len(env.provider.calls) == 4


def test_disabled_feature(make_env: Callable[..., Env], db_session: Session) -> None:
    env = make_env(ai_explanations_enabled=False)
    response = env.explain(env.guest())
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "AI_DISABLED"
    assert env.provider.calls == []
    assert outcomes(db_session) == ["disabled"]


# --- versions ------------------------------------------------------------------


def test_version_must_be_current_or_pinned(
    make_env: Callable[..., Env], run_import: Importer
) -> None:
    env = make_env()
    auth = env.guest()
    bad = env.explain(auth, version=str(uuid.uuid4()))
    assert bad.status_code == 422
    assert bad.json()["error"]["code"] == "VERSION_NOT_AVAILABLE"
    assert env.explain(auth, slug="draft-one", version=str(uuid.uuid4())).status_code == 404

    pinned = env.client.post("/v1/lessons/anchoring/attempts", headers=auth).json()
    v1 = pinned["attempt"]["lesson_version_id"]
    lessons = standard_lessons()
    lessons[0].update(version=2, title="Anchoring, revised")
    run_import(lessons)
    assert env.explain(auth, version=v1).status_code == 200  # open attempt pins v1
    assert env.explain(env.guest(), version=v1, mode="example").status_code == 422


# --- feedback ------------------------------------------------------------------


def test_two_incorrect_flags_hide_a_generated_explanation(
    make_env: Callable[..., Env], db_session: Session
) -> None:
    env = make_env()
    alice, bob, carol = env.guest(), env.guest(), env.guest()
    explanation = env.explain(alice).json()["explanation"]["id"]
    env.explain(bob)
    path = f"/v1/explanations/{explanation}/feedback"

    assert env.client.post(path, headers=carol, json={"rating": "incorrect"}).status_code == 404
    for _ in range(2):  # the same user flagging twice counts once
        assert env.client.post(path, headers=alice, json={"rating": "incorrect"}).status_code == 204
    row = db_session.get(AiExplanation, uuid.UUID(explanation))
    assert row is not None
    assert (row.flag_count, row.status) == (1, "generated")

    env.client.post(path, headers=bob, json={"rating": "incorrect"})
    db_session.refresh(row)
    assert (row.flag_count, row.status) == (2, "hidden")
    replacement = env.explain(carol).json()["explanation"]
    assert replacement["id"] != explanation
    assert replacement["variant"] == 2


def test_approved_explanations_are_not_auto_hidden(
    make_env: Callable[..., Env], db_session: Session
) -> None:
    env = make_env()
    alice, bob = env.guest(), env.guest()
    explanation = env.explain(alice).json()["explanation"]["id"]
    env.explain(bob)
    row = db_session.get(AiExplanation, uuid.UUID(explanation))
    assert row is not None
    row.status = "approved"
    db_session.flush()
    for auth in (alice, bob):
        env.client.post(
            f"/v1/explanations/{explanation}/feedback", headers=auth, json={"rating": "incorrect"}
        )
    db_session.refresh(row)
    assert (row.flag_count, row.status) == (2, "approved")
    assert env.explain(env.guest()).json()["explanation"]["label"] == "ai_reviewed"


def test_feedback_validation(make_env: Callable[..., Env]) -> None:
    env = make_env()
    auth = env.guest()
    explanation = env.explain(auth).json()["explanation"]["id"]
    bad = env.client.post(
        f"/v1/explanations/{explanation}/feedback", headers=auth, json={"rating": "meh"}
    )
    assert bad.status_code == 422
    unknown = env.client.post(
        f"/v1/explanations/{uuid.uuid4()}/feedback", headers=auth, json={"rating": "helpful"}
    )
    assert unknown.json()["error"]["code"] == "EXPLANATION_NOT_FOUND"


# --- privacy ------------------------------------------------------------------


def test_account_deletion_keeps_anonymous_usage_rows(
    make_env: Callable[..., Env], db_session: Session
) -> None:
    env = make_env(**PRICED)
    auth = env.guest()
    explanation = env.explain(auth).json()["explanation"]["id"]
    env.client.post(
        f"/v1/explanations/{explanation}/feedback", headers=auth, json={"rating": "helpful"}
    )
    env.client.request("DELETE", "/v1/me", headers=auth, json={"confirm": "DELETE"})
    db_session.expire_all()
    request = db_session.scalars(select(AiRequest)).one()
    assert request.user_id is None
    assert request.cost_micros == 10_000
    assert db_session.scalar(select(func.count()).select_from(AiExplanationFeedback)) == 0
    assert db_session.scalar(select(func.count()).select_from(AiExplanation)) == 1
