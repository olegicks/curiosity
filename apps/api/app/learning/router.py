"""/v1/lessons/{slug}/attempts and /v1/attempts/* (docs/spec/05 §5.5)."""

import uuid
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Response, status
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user, get_now
from app.auth.models import User
from app.core.db import get_db
from app.learning import discover, feedback, service
from app.learning.schemas import (
    AnswerIn,
    AnswerResponse,
    AttemptResponse,
    CompletionResponse,
    ContentFeedbackIn,
    ContentFeedbackOut,
    DiscoverOut,
    RatingIn,
    StartAttemptIn,
)

router = APIRouter(tags=["learning"])

NOT_FOUND: dict[int | str, dict[str, Any]] = {
    404: {"description": "Unknown or foreign attempt (ATTEMPT_NOT_FOUND)"}
}


@router.post(
    "/lessons/{slug}/attempts",
    response_model=AttemptResponse,
    status_code=status.HTTP_201_CREATED,
    responses={200: {"description": "An open attempt was resumed", "model": AttemptResponse}},
)
def start_attempt(
    response: Response,
    slug: Annotated[str, Path(max_length=60)],
    body: StartAttemptIn | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
) -> AttemptResponse:
    result, created = service.start_attempt(
        db, user.id, slug, restart=body.restart if body else False, now=now
    )
    if not created:
        response.status_code = status.HTTP_200_OK
    return result


@router.get("/attempts/{attempt_id}", response_model=AttemptResponse, responses=NOT_FOUND)
def get_attempt(
    attempt_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AttemptResponse:
    return service.get_attempt(db, user.id, attempt_id)


@router.post(
    "/attempts/{attempt_id}/answers",
    response_model=AnswerResponse,
    status_code=status.HTTP_201_CREATED,
    responses={**NOT_FOUND, 200: {"description": "Replay of a stored answer"}},
)
def submit_answer(
    response: Response,
    attempt_id: uuid.UUID,
    body: AnswerIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
) -> AnswerResponse:
    result, created = service.submit_answer(
        db,
        user.id,
        attempt_id,
        question_id=body.question_id,
        selected=body.selected_option_ids,
        value=body.value,
        now=now,
    )
    if not created:
        response.status_code = status.HTTP_200_OK
    return result


@router.post(
    "/attempts/{attempt_id}/complete", response_model=CompletionResponse, responses=NOT_FOUND
)
def complete_attempt(
    attempt_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
) -> CompletionResponse:
    return service.complete_attempt(db, user.id, attempt_id, now=now)


@router.get("/discover", response_model=DiscoverOut, tags=["discover"])
def get_discover(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
) -> DiscoverOut:
    return discover.discover(db, user.id, now)


@router.post(
    "/attempts/{attempt_id}/rating",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={**NOT_FOUND, 409: {"description": "Attempt not completed (ATTEMPT_NOT_COMPLETED)"}},
)
def rate_attempt(
    attempt_id: uuid.UUID,
    body: RatingIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
) -> Response:
    feedback.rate_attempt(db, user.id, attempt_id, body.rating, now)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/lessons/{slug}/feedback",
    response_model=ContentFeedbackOut,
    status_code=status.HTTP_201_CREATED,
    tags=["feedback"],
)
def report_problem(
    slug: Annotated[str, Path(max_length=60)],
    body: ContentFeedbackIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
) -> ContentFeedbackOut:
    return ContentFeedbackOut(id=feedback.submit_feedback(db, user.id, slug, body, now))
