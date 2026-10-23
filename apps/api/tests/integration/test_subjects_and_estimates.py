"""Lessons by subject and estimate questions end to end (D-17, D-18)."""

import copy
import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.content.models import AnswerOption
from tests.conftest import Importer
from tests.content_factory import SUBJECTS, make_lesson, standard_lessons

pytestmark = pytest.mark.db

ESTIMATE: dict[str, Any] = {
    "key": "check-2",
    "role": "lesson",
    "type": "estimate",
    "prompt": "How long is the Mississippi?",
    "estimate": {
        "min": 0,
        "max": 8000,
        "step": 100,
        "unit": "km",
        "answer": 3700,
        "tolerance": 600,
        "anchor": 7000,
    },
    "explanation": "About 3,700 km.",
}


@pytest.fixture
def content(run_import: Importer) -> None:
    lessons = standard_lessons()
    lessons[0]["questions"][1] = copy.deepcopy(ESTIMATE)
    subjects = copy.deepcopy(SUBJECTS)
    subjects["subjects"].append(
        {
            "slug": "math",
            "title": "Math",
            "description": "Chance and numbers.",
            "position": 2,
            "published": True,
            "topics": [{"slug": "chance", "title": "Chance", "description": "D.", "position": 1}],
        }
    )
    birthdays = make_lesson("birthdays", topic="chance", related=["anchoring"])
    birthdays["subject"] = "math"
    run_import([*lessons, birthdays], subjects=subjects)


def start(client: TestClient, auth: dict[str, str]) -> Any:
    return client.post("/v1/lessons/anchoring/attempts", headers=auth).json()


def answer(client: TestClient, auth: dict[str, str], attempt: str, body: dict[str, Any]) -> Any:
    return client.post(f"/v1/attempts/{attempt}/answers", headers=auth, json=body)


@pytest.mark.usefixtures("content")
def test_lessons_filter_by_subject(db_client: TestClient, auth: dict[str, str]) -> None:
    def items(**params: str) -> list[dict[str, Any]]:
        page = db_client.get("/v1/lessons", headers=auth, params=params).json()
        return list(page["items"])

    assert [i["slug"] for i in items(subject="math")] == ["birthdays"]
    assert [i["slug"] for i in items(subject="psychology")] == [
        "anchoring",
        "availability",
        "framing-effect",
    ]
    assert items(subject="unknown") == []
    assert items(subject="math")[0]["subject"] == {"slug": "math", "title": "Math"}
    subjects = db_client.get("/v1/subjects", headers=auth).json()["items"]
    assert [(s["slug"], s["description"]) for s in subjects] == [
        ("psychology", "How people think."),
        ("math", "Chance and numbers."),
    ]


@pytest.mark.usefixtures("content")
def test_estimate_is_graded_on_the_server(
    db_client: TestClient, auth: dict[str, str], db_session: Session
) -> None:
    body = start(db_client, auth)
    attempt = body["attempt"]["id"]
    choice, estimate = body["content"]["questions"]
    assert estimate["type"] == "estimate"
    assert estimate["options"] == []
    # the answer and tolerance stay on the server until the learner commits
    assert estimate["estimate"] == {
        "min": 0,
        "max": 8000,
        "step": 100,
        "unit": "km",
        "anchor": 7000,
    }

    def code(payload: dict[str, Any]) -> str:
        response = answer(db_client, auth, attempt, payload)
        assert response.status_code == 422, response.text
        return str(response.json()["error"]["code"])

    option = choice["options"][0]["id"]
    assert code({"question_id": estimate["id"], "value": 9000}) == "INVALID_VALUE"
    assert code({"question_id": estimate["id"], "selected_option_ids": [option]}) == "INVALID_VALUE"
    assert code({"question_id": choice["id"], "value": 10}) == "INVALID_OPTIONS"
    both = {"question_id": choice["id"], "selected_option_ids": [option], "value": 1}
    assert code(both) == "VALIDATION_ERROR"
    assert code({"question_id": choice["id"]}) == "VALIDATION_ERROR"

    graded = answer(db_client, auth, attempt, {"question_id": estimate["id"], "value": 5600})
    assert graded.status_code == 201
    assert graded.json()["is_correct"] is False
    assert graded.json()["estimate"] == {
        "value": 5600,
        "answer": 3700,
        "tolerance": 600,
        "unit": "km",
    }
    replay = answer(db_client, auth, attempt, {"question_id": estimate["id"], "value": 3700})
    assert replay.status_code == 200
    assert replay.json()["is_correct"] is False  # the first answer is final

    right = db_session.scalar(
        select(AnswerOption.id).where(
            AnswerOption.question_id == uuid.UUID(choice["id"]), AnswerOption.is_correct
        )
    )
    picked = {"question_id": choice["id"], "selected_option_ids": [str(right)]}
    assert answer(db_client, auth, attempt, picked).status_code == 201
    done = db_client.post(f"/v1/attempts/{attempt}/complete", headers=auth).json()
    assert done["attempt"]["correct_first_try"] == 1
    resumed = db_client.get(f"/v1/attempts/{attempt}", headers=auth).json()
    stored = next(a for a in resumed["attempt"]["answers"] if a["question_id"] == estimate["id"])
    assert stored["estimate"]["value"] == 5600


@pytest.mark.usefixtures("content")
def test_close_estimate_is_correct(db_client: TestClient, auth: dict[str, str]) -> None:
    body = start(db_client, auth)
    estimate = body["content"]["questions"][1]
    payload = {"question_id": estimate["id"], "value": 4200}
    assert answer(db_client, auth, body["attempt"]["id"], payload).json()["is_correct"] is True
