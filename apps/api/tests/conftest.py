"""Shared fixtures.

DB-backed tests are marked ``db`` and run against real PostgreSQL at
TEST_DATABASE_URL. When it is unset they are skipped (CI always sets it).
"""

import os
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from typing import Any

import pytest
from alembic import command
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from app import models  # noqa: F401  # register all tables on Base.metadata
from app.config import AppEnv, Settings
from app.core.clock import FixedClock
from app.core.db import alembic_config, get_db
from app.main import create_app

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
# Nothing listens on port 1: DB calls fail fast without a real database.
UNREACHABLE_DATABASE_URL = "postgresql+psycopg://nobody:nothing@127.0.0.1:1/none"
TEST_JWT_SECRET = "test-secret-test-secret-test-secret-0123"
TEST_NOW = datetime(2026, 11, 2, 12, 0, tzinfo=UTC)


def make_settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "app_env": AppEnv.TEST,
        "database_url": UNREACHABLE_DATABASE_URL,
        "db_connect_timeout_seconds": 1,
        "git_sha": "test-sha",
        "log_level": "WARNING",
        "jwt_secret": TEST_JWT_SECRET,
        "rate_limit_enabled": False,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if TEST_DATABASE_URL:
        return
    skip_db = pytest.mark.skip(reason="TEST_DATABASE_URL not set; PostgreSQL tests skipped")
    for item in items:
        if "db" in item.keywords:
            item.add_marker(skip_db)


@pytest.fixture
def app() -> FastAPI:
    return create_app(make_settings())


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


# --- PostgreSQL fixtures ---------------------------------------------------------------


@pytest.fixture(scope="session")
def db_engine() -> Iterator[Engine]:
    assert TEST_DATABASE_URL, "db fixtures require TEST_DATABASE_URL"
    command.upgrade(alembic_config(TEST_DATABASE_URL), "head")
    engine = create_engine(TEST_DATABASE_URL)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(db_engine: Engine) -> Iterator[Session]:
    """Session inside an outer transaction that is rolled back after the test."""
    with db_engine.connect() as connection:
        transaction = connection.begin()
        session = Session(bind=connection, join_transaction_mode="create_savepoint")
        try:
            yield session
        finally:
            session.close()
            transaction.rollback()


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock(TEST_NOW)


@pytest.fixture
def make_db_client(db_session: Session, clock: FixedClock) -> Iterator[Callable[..., TestClient]]:
    """Build clients sharing the rolled-back test session and the fixed clock."""
    clients: list[TestClient] = []

    def factory(**settings_overrides: Any) -> TestClient:
        assert TEST_DATABASE_URL
        application = create_app(
            make_settings(database_url=TEST_DATABASE_URL, **settings_overrides), clock=clock
        )
        application.dependency_overrides[get_db] = lambda: db_session
        test_client = TestClient(application, raise_server_exceptions=False)
        test_client.__enter__()
        clients.append(test_client)
        return test_client

    yield factory
    for test_client in clients:
        test_client.__exit__(None, None, None)


@pytest.fixture
def db_client(make_db_client: Callable[..., TestClient]) -> TestClient:
    return make_db_client()
