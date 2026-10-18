"""Application errors and the uniform error envelope (docs/spec/05-api.md §5.1)."""

from typing import Any

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_request_id

log = structlog.get_logger(__name__)


class AppError(Exception):
    """Base class for errors that map to an API error response."""

    status_code: int = 400
    code: str = "BAD_REQUEST"
    message: str = "Bad request."

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        details: list[dict[str, Any]] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.message = message or self.message
        self.code = code or self.code
        self.details = details or []
        self.headers = headers
        super().__init__(self.message)


class BadRequestError(AppError):
    status_code = 400
    code = "BAD_REQUEST"
    message = "Bad request."


class UnauthenticatedError(AppError):
    status_code = 401
    code = "UNAUTHENTICATED"
    message = "Authentication required."


class ForbiddenError(AppError):
    status_code = 403
    code = "FORBIDDEN"
    message = "Not allowed."


class NotFoundError(AppError):
    status_code = 404
    code = "NOT_FOUND"
    message = "Not found."


class ConflictError(AppError):
    status_code = 409
    code = "CONFLICT"
    message = "Conflict."


class ValidationError(AppError):
    status_code = 422
    code = "VALIDATION_ERROR"
    message = "Request validation failed."


class UpgradeRequiredError(AppError):
    status_code = 426
    code = "UPGRADE_REQUIRED"
    message = "Please update the app to continue."


class RateLimitedError(AppError):
    status_code = 429
    code = "RATE_LIMITED"
    message = "Too many requests."


class ServiceUnavailableError(AppError):
    status_code = 503
    code = "SERVICE_UNAVAILABLE"
    message = "Service temporarily unavailable."


_HTTP_STATUS_CODES = {
    400: "BAD_REQUEST",
    401: "UNAUTHENTICATED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    413: "PAYLOAD_TOO_LARGE",
    415: "UNSUPPORTED_MEDIA_TYPE",
}


def error_response(
    status_code: int,
    code: str,
    message: str,
    details: list[dict[str, Any]] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    body = {
        "error": {
            "code": code,
            "message": message,
            "details": details or [],
            "request_id": get_request_id(),
        }
    }
    return JSONResponse(status_code=status_code, content=body, headers=headers)


def internal_error_response() -> JSONResponse:
    return error_response(500, "INTERNAL_ERROR", "Internal server error.")


async def _handle_app_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)  # noqa: S101 - registered for AppError only
    return error_response(exc.status_code, exc.code, exc.message, exc.details, exc.headers)


async def _handle_validation_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)  # noqa: S101
    errors = exc.errors()
    if any(err.get("type") == "json_invalid" for err in errors):
        return error_response(400, "BAD_REQUEST", "Malformed JSON body.")
    details = [
        {
            # loc is e.g. ("body", "email"); drop the source prefix for readability
            "field": ".".join(str(part) for part in err.get("loc", ())[1:]) or None,
            "issue": err.get("type", "invalid"),
        }
        for err in errors
    ]
    return error_response(422, "VALIDATION_ERROR", "Request validation failed.", details)


async def _handle_http_exception(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)  # noqa: S101
    code = _HTTP_STATUS_CODES.get(exc.status_code, "HTTP_ERROR")
    headers = dict(exc.headers) if exc.headers else None
    return error_response(exc.status_code, code, "Request could not be processed.", None, headers)


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _handle_app_error)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
    app.add_exception_handler(StarletteHTTPException, _handle_http_exception)
