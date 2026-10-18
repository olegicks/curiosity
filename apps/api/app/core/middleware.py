"""Request context (request id + access log) and the minimum app-version gate."""

import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from app.config import parse_version
from app.core.errors import error_response, internal_error_response
from app.core.ids import uuid7
from app.core.logging import clear_request_context, set_request_id

log = structlog.get_logger("app.access")

REQUEST_ID_HEADER = "X-Request-ID"
APP_VERSION_HEADER = "X-App-Version"


def _incoming_request_id(request: Request) -> str:
    raw = request.headers.get(REQUEST_ID_HEADER)
    if raw:
        try:
            return str(uuid.UUID(raw))
        except ValueError:
            pass  # ignore malformed client ids
    return str(uuid7())


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Assigns a request id, logs one access line, and converts unhandled errors to 500s."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        clear_request_context()
        request_id = _incoming_request_id(request)
        set_request_id(request_id)
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            log.exception("unhandled_error", method=request.method, path=request.url.path)
            response = internal_error_response()
        duration_ms = round((time.perf_counter() - started) * 1000, 1)
        response.headers[REQUEST_ID_HEADER] = request_id
        route = request.scope.get("route")
        log.info(
            "request",
            method=request.method,
            route=getattr(route, "path", None),
            path=request.url.path,
            status=response.status_code,
            duration_ms=duration_ms,
        )
        return response


class AppVersionGateMiddleware(BaseHTTPMiddleware):
    """Rejects clients older than MIN_APP_VERSION with 426 (health checks are exempt).

    Requests without the header are allowed so that tooling and health checks work.
    """

    def __init__(self, app: ASGIApp, min_version: tuple[int, int, int]) -> None:
        super().__init__(app)
        self.min_version = min_version

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        raw = request.headers.get(APP_VERSION_HEADER)
        if raw is not None and not request.url.path.startswith("/health"):
            try:
                version = parse_version(raw)
            except ValueError:
                return error_response(
                    400,
                    "BAD_REQUEST",
                    "Invalid X-App-Version header.",
                    [{"field": APP_VERSION_HEADER, "issue": "invalid_version"}],
                )
            if version < self.min_version:
                return error_response(426, "UPGRADE_REQUIRED", "Please update the app to continue.")
        return await call_next(request)
