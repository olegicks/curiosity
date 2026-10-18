"""Structured JSON logging with a per-request id.

Never log emails, tokens, passwords, answer text or AI prompts; user ids only.
"""

import logging
import sys
from contextvars import ContextVar

import structlog

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)


def get_request_id() -> str | None:
    return _request_id.get()


def set_request_id(request_id: str) -> None:
    _request_id.set(request_id)
    structlog.contextvars.bind_contextvars(request_id=request_id)


def clear_request_context() -> None:
    _request_id.set(None)
    structlog.contextvars.clear_contextvars()


def configure_logging(level: str, *, json: bool) -> None:
    shared: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    renderer: structlog.types.Processor = (
        structlog.processors.JSONRenderer() if json else structlog.dev.ConsoleRenderer()
    )
    structlog.configure(
        processors=[*shared, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(level)),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=False,
    )
    # Route stdlib loggers (uvicorn, sqlalchemy, alembic) to stdout at the same level.
    logging.basicConfig(level=level, stream=sys.stdout, format="%(message)s", force=True)
    logging.getLogger("uvicorn.access").disabled = True  # replaced by our access log
