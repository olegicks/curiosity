"""Liveness and readiness probes, mounted outside /v1 (docs/spec/05-api.md §5.10)."""

from typing import Literal

import structlog
from fastapi import APIRouter, Request
from pydantic import BaseModel
from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError

from app.core import db
from app.core.errors import ServiceUnavailableError

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/health", tags=["health"])


class LivenessOut(BaseModel):
    status: Literal["ok"]
    version: str


class ReadinessOut(BaseModel):
    status: Literal["ready"]


@router.get("", response_model=LivenessOut)
def liveness(request: Request) -> LivenessOut:
    return LivenessOut(status="ok", version=request.app.state.settings.git_sha)


@router.get(
    "/ready",
    response_model=ReadinessOut,
    responses={503: {"description": "Database unreachable or migrations pending"}},
)
def readiness(request: Request) -> ReadinessOut:
    engine: Engine = request.app.state.engine
    try:
        db.ping(engine)
        pending = db.pending_migrations(engine)
    except SQLAlchemyError:
        log.warning("readiness_db_unreachable")
        raise ServiceUnavailableError("Database unavailable.") from None
    if pending:
        log.warning("readiness_migrations_pending")
        raise ServiceUnavailableError("Database migrations pending.")
    return ReadinessOut(status="ready")
