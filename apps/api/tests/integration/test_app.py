"""App-level behaviour that needs no database: envelopes, middleware, health."""

import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

from app.config import AppEnv
from app.core.errors import ConflictError
from app.main import create_app
from tests.conftest import make_settings


class EchoIn(BaseModel):
    name: str = Field(min_length=1, max_length=5)


def _app_with_test_routes(**settings: object) -> FastAPI:
    app = create_app(make_settings(**settings))

    @app.post("/v1/_test/echo")
    def echo(body: EchoIn) -> EchoIn:
        return body

    @app.get("/v1/_test/conflict")
    def conflict() -> None:
        raise ConflictError("Already done.", code="ALREADY_DONE", details=[{"id": "x"}])

    @app.get("/v1/_test/boom")
    def boom() -> None:
        raise RuntimeError("secret internal detail")

    return app


@pytest.fixture
def test_client() -> TestClient:
    return TestClient(_app_with_test_routes(), raise_server_exceptions=False)


def _assert_envelope(body: dict[str, object], code: str) -> dict[str, object]:
    error = body["error"]
    assert isinstance(error, dict)
    assert error["code"] == code
    assert set(error) == {"code", "message", "details", "request_id"}
    assert uuid.UUID(str(error["request_id"]))
    return error


def test_liveness_reports_version(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "test-sha"}


def test_readiness_returns_503_when_database_unreachable(client: TestClient) -> None:
    response = client.get("/health/ready")
    assert response.status_code == 503
    _assert_envelope(response.json(), "SERVICE_UNAVAILABLE")


def test_request_id_is_generated_and_echoed(client: TestClient) -> None:
    generated = client.get("/health").headers["X-Request-ID"]
    assert uuid.UUID(generated).version == 7

    supplied = str(uuid.uuid4())
    assert client.get("/health", headers={"X-Request-ID": supplied}).headers["X-Request-ID"] == (
        supplied
    )


def test_malformed_request_id_is_replaced(client: TestClient) -> None:
    returned = client.get("/health", headers={"X-Request-ID": "not-a-uuid"}).headers["X-Request-ID"]
    assert uuid.UUID(returned)


def test_unknown_route_uses_error_envelope(client: TestClient) -> None:
    response = client.get("/v1/does-not-exist")
    assert response.status_code == 404
    error = _assert_envelope(response.json(), "NOT_FOUND")
    assert error["request_id"] == response.headers["X-Request-ID"]


def test_method_not_allowed_uses_error_envelope(client: TestClient) -> None:
    response = client.post("/health")
    assert response.status_code == 405
    _assert_envelope(response.json(), "METHOD_NOT_ALLOWED")


def test_validation_error_lists_fields(test_client: TestClient) -> None:
    response = test_client.post("/v1/_test/echo", json={"name": "far too long"})
    assert response.status_code == 422
    error = _assert_envelope(response.json(), "VALIDATION_ERROR")
    assert error["details"] == [{"field": "name", "issue": "string_too_long"}]


def test_malformed_json_is_bad_request(test_client: TestClient) -> None:
    response = test_client.post(
        "/v1/_test/echo", content=b"{not json", headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 400
    _assert_envelope(response.json(), "BAD_REQUEST")


def test_app_error_renders_code_and_details(test_client: TestClient) -> None:
    response = test_client.get("/v1/_test/conflict")
    assert response.status_code == 409
    error = _assert_envelope(response.json(), "ALREADY_DONE")
    assert error["message"] == "Already done."
    assert error["details"] == [{"id": "x"}]


def test_unhandled_error_hides_internals(test_client: TestClient) -> None:
    response = test_client.get("/v1/_test/boom")
    assert response.status_code == 500
    error = _assert_envelope(response.json(), "INTERNAL_ERROR")
    assert "secret" not in response.text
    assert error["request_id"] == response.headers["X-Request-ID"]


@pytest.mark.parametrize(
    ("version", "status"), [("0.9.9", 426), ("1.0.0", 404), ("1.2.0", 404), ("garbage", 400)]
)
def test_app_version_gate(client: TestClient, version: str, status: int) -> None:
    # /v1/does-not-exist returns 404 once the gate lets the request through
    response = client.get("/v1/does-not-exist", headers={"X-App-Version": version})
    assert response.status_code == status
    assert "X-Request-ID" in response.headers
    if status == 426:
        _assert_envelope(response.json(), "UPGRADE_REQUIRED")


def test_health_is_exempt_from_version_gate(client: TestClient) -> None:
    assert client.get("/health", headers={"X-App-Version": "0.0.1"}).status_code == 200


def test_openapi_hidden_in_production() -> None:
    prod = TestClient(create_app(make_settings(app_env=AppEnv.PRODUCTION)))
    assert prod.get("/v1/openapi.json").status_code == 404
    local = TestClient(create_app(make_settings(app_env=AppEnv.STAGING)))
    assert local.get("/v1/openapi.json").status_code == 200
