"""Integration-test helpers: a time-travelling learner and answer shortcuts."""

import uuid
from datetime import timedelta
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.content.models import AnswerOption
from app.core.clock import FixedClock


class Learner:
    """A guest whose tokens are refreshed after the test clock jumps forward."""

    def __init__(self, client: TestClient, clock: FixedClock) -> None:
        self.client, self.clock = client, clock
        self.tokens = client.post("/v1/auth/guest", json={}).json()["tokens"]

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.tokens['access_token']}"}

    def travel(self, days: int = 0, **kwargs: int) -> None:
        """Advance the clock, refreshing at least every 29 days (refresh tokens last 30)."""
        remaining = timedelta(days=days, **kwargs)
        while True:
            step = min(remaining, timedelta(days=29))
            self.clock.advance(step)
            remaining -= step
            refreshed = self.client.post(
                "/v1/auth/refresh", json={"refresh_token": self.tokens["refresh_token"]}
            )
            assert refreshed.status_code == 200, refreshed.text
            self.tokens = refreshed.json()["tokens"]
            if remaining <= timedelta(0):
                break

    def get(self, path: str, **kwargs: Any) -> Any:
        return self.client.get(path, headers=self.headers, **kwargs)

    def post(self, path: str, json: Any = None) -> Any:
        return self.client.post(path, headers=self.headers, json=json)


def correct_ids(db: Session, question_id: str) -> list[str]:
    return [
        str(i)
        for i in db.scalars(
            select(AnswerOption.id).where(
                AnswerOption.question_id == uuid.UUID(question_id), AnswerOption.is_correct
            )
        )
    ]


def wrong_ids(db: Session, question_id: str) -> list[str]:
    ids = db.scalars(
        select(AnswerOption.id).where(
            AnswerOption.question_id == uuid.UUID(question_id), AnswerOption.is_correct.is_(False)
        )
    )
    return [str(next(iter(ids)))]


def complete_lesson(learner: Learner, db: Session, slug: str = "anchoring") -> None:
    body = learner.post(f"/v1/lessons/{slug}/attempts").json()
    for q in body["content"]["questions"]:
        learner.post(
            f"/v1/attempts/{body['attempt']['id']}/answers",
            {"question_id": q["id"], "selected_option_ids": correct_ids(db, q["id"])},
        )
    assert learner.post(f"/v1/attempts/{body['attempt']['id']}/complete").status_code == 200


def review_once(learner: Learner, db: Session, *, correct: bool, guessed: bool = False) -> Any:
    session = learner.post("/v1/review-sessions").json()["session"]
    item = session["items"][0]
    ids = (
        correct_ids(db, item["question"]["id"])
        if correct
        else wrong_ids(db, item["question"]["id"])
    )
    response = learner.post(
        f"/v1/review-sessions/{session['id']}/items/{item['id']}/answer",
        {"selected_option_ids": ids, "guessed": guessed},
    )
    assert response.status_code == 201, response.text
    return response.json()
