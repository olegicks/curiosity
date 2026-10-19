"""/v1/lessons/{slug}/explanations and /v1/explanations/{id}/feedback (docs/spec/05 §5.8)."""

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Request, Response, status
from sqlalchemy.orm import Session

from app.ai import service
from app.ai.provider import ExplanationProvider
from app.ai.schemas import ExplanationIn, ExplanationResponse, FeedbackIn
from app.auth.deps import get_current_user, get_now, get_settings_dep
from app.auth.models import User
from app.config import Settings
from app.core.db import get_db

router = APIRouter(tags=["ai"])


def get_provider(request: Request) -> ExplanationProvider:
    provider: ExplanationProvider = request.app.state.ai_provider
    return provider


@router.post(
    "/lessons/{slug}/explanations",
    response_model=ExplanationResponse,
    responses={
        429: {"description": "Per-user limit reached (AI_RATE_LIMITED)"},
        503: {"description": "AI_UNAVAILABLE (provider, timeout, quality, budget) or AI_DISABLED"},
    },
)
def request_explanation(
    slug: Annotated[str, Path(max_length=60)],
    body: ExplanationIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
    settings: Settings = Depends(get_settings_dep),
    provider: ExplanationProvider = Depends(get_provider),
) -> ExplanationResponse:
    return service.explain(
        db,
        user.id,
        slug,
        mode=body.mode,
        version_id=body.lesson_version_id,
        exclude_ids=body.exclude_ids,
        now=now,
        settings=settings,
        provider=provider,
    )


@router.post("/explanations/{explanation_id}/feedback", status_code=status.HTTP_204_NO_CONTENT)
def explanation_feedback(
    explanation_id: uuid.UUID,
    body: FeedbackIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    service.record_feedback(db, user.id, explanation_id, body.rating)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
