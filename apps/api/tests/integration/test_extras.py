"""Lesson rating, content feedback, analytics events, data export, editorial CLI."""

import json
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from typer.testing import CliRunner

from app import cli
from app.ai import admin
from app.ai.models import AiExplanation, AiRequest
from app.ai.provider import FakeProvider, ProviderError
from app.analytics.models import ProductEvent
from app.core.clock import FixedClock
from app.learning.models import ContentFeedback, LessonRating
from tests.conftest import TEST_NOW, Importer, make_settings
from tests.content_factory import standard_lessons
from tests.helpers import Learner, complete_lesson, correct_ids

pytestmark = pytest.mark.db


@pytest.fixture
def learner(db_client: TestClient, clock: FixedClock, run_import: Importer) -> Learner:
    run_import(standard_lessons())
    return Learner(db_client, clock)


def completed_attempt(learner: Learner, db: Session, slug: str = "anchoring") -> dict[str, Any]:
    body: dict[str, Any] = learner.post(f"/v1/lessons/{slug}/attempts").json()
    for q in body["content"]["questions"]:
        learner.post(
            f"/v1/attempts/{body['attempt']['id']}/answers",
            {"question_id": q["id"], "selected_option_ids": correct_ids(db, q["id"])},
        )
    learner.post(f"/v1/attempts/{body['attempt']['id']}/complete")
    return body


# --- lesson rating ---------------------------------------------------------------------------


def test_rating_is_upserted_for_completed_attempts(learner: Learner, db_session: Session) -> None:
    open_attempt = learner.post("/v1/lessons/availability/attempts").json()["attempt"]["id"]
    early = learner.post(f"/v1/attempts/{open_attempt}/rating", {"rating": "clear"})
    assert early.status_code == 409
    assert early.json()["error"]["code"] == "ATTEMPT_NOT_COMPLETED"

    attempt = completed_attempt(learner, db_session)["attempt"]["id"]
    assert learner.post(f"/v1/attempts/{attempt}/rating", {"rating": "clear"}).status_code == 204
    assert learner.post(f"/v1/attempts/{attempt}/rating", {"rating": "unclear"}).status_code == 204
    rating = db_session.scalars(select(LessonRating)).one()
    assert rating.rating == "unclear"

    other = Learner(learner.client, learner.clock)
    assert other.post(f"/v1/attempts/{attempt}/rating", {"rating": "clear"}).status_code == 404
    assert learner.post(f"/v1/attempts/{attempt}/rating", {"rating": "great"}).status_code == 422


# --- content feedback ------------------------------------------------------------------------


def test_report_a_problem(learner: Learner, db_session: Session) -> None:
    lesson = learner.get("/v1/lessons/anchoring").json()
    version = lesson["content"]["lesson_version_id"]
    question = lesson["content"]["questions"][0]["id"]
    response = learner.post(
        "/v1/lessons/anchoring/feedback",
        {
            "kind": "factual_error",
            "message": "  The date looks wrong.  ",
            "question_id": question,
            "lesson_version_id": version,
        },
    )
    assert response.status_code == 201
    row = db_session.get(ContentFeedback, uuid.UUID(response.json()["id"]))
    assert row is not None
    assert (row.kind, row.message, row.status) == ("factual_error", "The date looks wrong.", "open")

    other_version = learner.get("/v1/lessons/availability").json()["content"]["lesson_version_id"]
    mismatch = learner.post(
        "/v1/lessons/anchoring/feedback", {"kind": "typo", "lesson_version_id": other_version}
    )
    assert mismatch.json()["error"]["code"] == "INVALID_REFERENCE"
    foreign_question = learner.post(
        "/v1/lessons/anchoring/feedback",
        {"kind": "typo", "lesson_version_id": version, "question_id": str(uuid.uuid4())},
    )
    assert foreign_question.json()["error"]["details"] == [
        {"field": "question_id", "issue": "mismatch"}
    ]
    assert (
        learner.post(
            "/v1/lessons/draft-one/feedback", {"kind": "typo", "lesson_version_id": version}
        ).status_code
        == 404
    )
    too_long = learner.post(
        "/v1/lessons/anchoring/feedback",
        {"kind": "other", "lesson_version_id": version, "message": "x" * 501},
    )
    assert too_long.status_code == 422


def test_feedback_is_limited_per_day_and_survives_account_deletion(
    learner: Learner, db_session: Session
) -> None:
    version = learner.get("/v1/lessons/anchoring").json()["content"]["lesson_version_id"]
    body = {"kind": "typo", "lesson_version_id": version}
    statuses = [learner.post("/v1/lessons/anchoring/feedback", body).status_code for _ in range(11)]
    assert statuses == [201] * 10 + [429]
    learner.travel(days=1, minutes=1)
    assert learner.post("/v1/lessons/anchoring/feedback", body).status_code == 201

    learner.client.request("DELETE", "/v1/me", headers=learner.headers, json={"confirm": "DELETE"})
    db_session.expire_all()
    rows = db_session.scalars(select(ContentFeedback)).all()
    assert len(rows) == 11
    assert all(r.user_id is None for r in rows)


# --- analytics events -------------------------------------------------------------------------


def test_events_are_whitelisted_and_clamped(learner: Learner, db_session: Session) -> None:
    learner.client.patch(
        "/v1/me/preferences", headers=learner.headers, json={"timezone": "Pacific/Auckland"}
    )
    events = [
        {
            "name": "app_opened",
            "occurred_at": "2026-11-02T11:59:00Z",
            "properties": {"cold_start": True, "device": "x"},
        },
        {
            "name": "screen_viewed",
            "occurred_at": "2026-11-02T11:59:00Z",
            "properties": {"screen": "nowhere"},
        },
        {"name": "made_up", "occurred_at": "2026-11-02T11:59:00Z"},
        {
            "name": "onboarding_step",
            "occurred_at": "2026-10-01T00:00:00Z",
            "properties": {"step": "goal", "action": "skip"},
        },
    ]
    response = learner.client.post(
        "/v1/events",
        headers={**learner.headers, "X-Platform": "ios", "X-App-Version": "1.2.3"},
        json={"events": events},
    )
    assert response.status_code == 202
    assert response.json() == {"accepted": 2, "rejected": 2}

    rows = {
        e.name: e
        for e in db_session.scalars(
            select(ProductEvent).where(ProductEvent.name.in_(["app_opened", "onboarding_step"]))
        )
    }
    assert rows["app_opened"].properties == {"cold_start": True}  # unknown key dropped
    assert (rows["app_opened"].platform, rows["app_opened"].app_version) == ("ios", "1.2.3")
    assert rows["app_opened"].local_date.isoformat() == "2026-11-03"  # Auckland
    assert rows["onboarding_step"].occurred_at == TEST_NOW - timedelta(days=7)  # clamped


def test_events_payload_validation(learner: Learner) -> None:
    naive = learner.post(
        "/v1/events", {"events": [{"name": "app_opened", "occurred_at": "2026-11-02T11:00:00"}]}
    )
    assert naive.status_code == 422
    event = {
        "name": "app_opened",
        "occurred_at": "2026-11-02T11:00:00Z",
        "properties": {"cold_start": False},
    }
    assert learner.post("/v1/events", {"events": [event] * 21}).status_code == 422
    assert learner.post("/v1/events", {"events": []}).status_code == 422


def test_events_rate_limit(
    make_db_client: Callable[..., TestClient], clock: FixedClock, run_import: Importer
) -> None:
    run_import(standard_lessons())
    learner = Learner(make_db_client(rate_limit_enabled=True), clock)
    event = {
        "name": "app_opened",
        "occurred_at": "2026-11-02T11:00:00Z",
        "properties": {"cold_start": True},
    }
    statuses = [learner.post("/v1/events", {"events": [event]}).status_code for _ in range(61)]
    assert statuses[-2:] == [202, 429]


def test_server_events_and_anonymised_deletion(learner: Learner, db_session: Session) -> None:
    learner.post(
        "/v1/auth/upgrade", {"email": "maya@example.com", "password": "a sensible passphrase"}
    )
    names = list(db_session.scalars(select(ProductEvent.name).order_by(ProductEvent.id)))
    assert names == ["guest_created", "account_upgraded"]

    tokens = learner.client.post(
        "/v1/auth/login", json={"email": "maya@example.com", "password": "a sensible passphrase"}
    ).json()["tokens"]
    learner.client.request(
        "DELETE",
        "/v1/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
        json={"password": "a sensible passphrase"},
    )
    db_session.expire_all()
    remaining = db_session.scalars(select(ProductEvent)).all()
    assert [(e.name, e.user_id, e.properties) for e in remaining] == [
        ("account_deleted", None, {"was_guest": False})
    ]


# --- data export -------------------------------------------------------------------------------


def test_export_contains_everything_and_nothing_else(learner: Learner, db_session: Session) -> None:
    complete_lesson(learner, db_session, "anchoring")
    other = Learner(learner.client, learner.clock)
    complete_lesson(other, db_session, "availability")
    other_id = other.get("/v1/me").json()["user"]["id"]
    learner.travel(days=1)
    session = learner.post("/v1/review-sessions").json()["session"]
    item = session["items"][0]
    learner.post(
        f"/v1/review-sessions/{session['id']}/items/{item['id']}/answer",
        {"selected_option_ids": correct_ids(db_session, item["question"]["id"])},
    )

    response = learner.get("/v1/me/export")
    assert response.status_code == 200
    assert response.headers["content-disposition"] == (
        'attachment; filename="curiosity-export-2026-11-03.json"'
    )
    data = response.json()
    for key in [
        "user", "preferences", "interest_topics", "lesson_attempts", "lesson_progress",
        "lesson_ratings", "content_feedback", "review_states", "review_sessions",
        "review_events", "xp_transactions", "streak", "daily_activity", "achievements",
        "ai_explanation_feedback", "product_events",
    ]:  # fmt: skip
        assert key in data
    assert data["format_version"] == 1
    assert "password_hash" not in data["user"]
    assert "token_version" not in data["user"]
    assert len(data["lesson_attempts"]) == 1
    assert len(data["lesson_attempts"][0]["answers"]) == 2
    assert len(data["review_sessions"][0]["items"]) == 1
    assert len(data["review_events"]) == 1
    assert data["streak"]["current_streak"] == 2
    text = json.dumps(data)
    assert other_id not in text


def test_export_rate_limit(
    make_db_client: Callable[..., TestClient], clock: FixedClock, run_import: Importer
) -> None:
    run_import(standard_lessons())
    learner = Learner(make_db_client(rate_limit_enabled=True), clock)
    statuses = [learner.get("/v1/me/export").status_code for _ in range(4)]
    assert statuses == [200, 200, 200, 429]


# --- AI editorial tools -------------------------------------------------------------------------


def test_pregenerate_creates_missing_variants_once(
    run_import: Importer, db_session: Session
) -> None:
    run_import(standard_lessons())
    provider = FakeProvider()
    settings = make_settings()
    first = admin.pregenerate(
        db_session, settings=settings, provider=provider, max_cost_micros=10**9
    )
    assert len(first.created) == 9  # 3 published lessons x 3 modes
    second = admin.pregenerate(
        db_session, settings=settings, provider=provider, max_cost_micros=10**9
    )
    assert (len(second.created), second.skipped) == (0, 9)
    assert db_session.scalar(select(func.count()).select_from(AiRequest)) == 0
    assert all(e.status == "generated" for e in db_session.scalars(select(AiExplanation)))


def test_pregenerate_stops_at_cost_limit_and_reports_failures(
    run_import: Importer, db_session: Session
) -> None:
    run_import(standard_lessons())
    priced = make_settings(ai_price_input_per_mtok_micros=4_000_000)
    capped = admin.pregenerate(
        db_session, settings=priced, provider=FakeProvider(), max_cost_micros=10_000
    )
    assert len(capped.created) == 2  # 6,000 micro-USD each
    assert capped.stopped_by_budget is True

    failing = FakeProvider()
    failing.script.extend([ProviderError("down")])
    result = admin.pregenerate(
        db_session, settings=make_settings(), provider=failing, max_cost_micros=10**9
    )
    assert len(result.failed) == 1
    assert len(result.created) == 6


def test_review_cli_and_status_changes(
    run_import: Importer, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_import(standard_lessons())
    admin.pregenerate(
        db_session, settings=make_settings(), provider=FakeProvider(), max_cost_micros=10**9
    )

    @contextmanager
    def test_session() -> Iterator[Session]:
        yield db_session

    monkeypatch.setattr(cli, "_session", test_session)
    runner = CliRunner()
    result = runner.invoke(cli.app, ["ai", "review"], input="a\nr\ns\nq\n")
    assert result.exit_code == 0, result.output
    assert "reviewed 2 of 9" in result.output
    statuses = sorted(e.status for e in db_session.scalars(select(AiExplanation)))
    assert statuses.count("approved") == 1
    assert statuses.count("rejected") == 1

    explanation = db_session.scalars(
        select(AiExplanation).where(AiExplanation.status == "generated")
    ).first()
    assert explanation is not None
    ok = runner.invoke(cli.app, ["ai", "set-status", str(explanation.id), "hidden"])
    assert ok.exit_code == 0
    assert db_session.get(AiExplanation, explanation.id).status == "hidden"  # type: ignore[union-attr]
    bad = runner.invoke(cli.app, ["ai", "set-status", str(explanation.id), "published"])
    assert bad.exit_code == 1
    listed = runner.invoke(cli.app, ["ai", "list", "--flagged"])
    assert "1 explanation(s)" in listed.output


def test_feedback_cli(
    learner: Learner, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    version = learner.get("/v1/lessons/anchoring").json()["content"]["lesson_version_id"]
    report = learner.post(
        "/v1/lessons/anchoring/feedback",
        {"kind": "unclear", "message": "Step two\nis confusing", "lesson_version_id": version},
    ).json()["id"]

    @contextmanager
    def test_session() -> Iterator[Session]:
        yield db_session

    monkeypatch.setattr(cli, "_session", test_session)
    runner = CliRunner()
    listed = runner.invoke(cli.app, ["content", "feedback", "list"])
    assert "anchoring  unclear  Step two is confusing" in listed.output
    resolved = runner.invoke(
        cli.app, ["content", "feedback", "resolve", report, "--note", "fixed in abc123"]
    )
    assert resolved.exit_code == 0
    row = db_session.get(ContentFeedback, uuid.UUID(report))
    assert row is not None
    assert (row.status, row.resolution_note) == ("resolved", "fixed in abc123")
    assert row.resolved_at is not None
    assert "0 report(s)" in runner.invoke(cli.app, ["content", "feedback", "list"]).output
    missing = runner.invoke(cli.app, ["content", "feedback", "resolve", str(uuid.uuid4())])
    assert missing.exit_code == 1
