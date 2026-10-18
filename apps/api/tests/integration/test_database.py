"""Checks that need a real PostgreSQL (skipped without TEST_DATABASE_URL)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

pytestmark = pytest.mark.db


def test_session_executes_queries(db_session: Session) -> None:
    assert db_session.execute(text("SELECT 1")).scalar_one() == 1


def test_readiness_ok_when_migrated(db_client: TestClient) -> None:
    response = db_client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
