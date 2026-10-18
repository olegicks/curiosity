"""/v1/reviews/* and /v1/review-sessions/* (docs/spec/05 §5.6)."""

import uuid
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user, get_now
from app.auth.models import User
from app.core.db import get_db
from app.reviews import service
from app.reviews.schemas import (
    ConceptPage,
    ReviewAnswerIn,
    ReviewAnswerResponse,
    ReviewSummaryOut,
    SessionResponse,
)

router = APIRouter(tags=["reviews"])

SESSION_NOT_FOUND: dict[int | str, dict[str, Any]] = {
    404: {"description": "Unknown or foreign session (SESSION_NOT_FOUND)"}
}


@router.get("/reviews/summary", response_model=ReviewSummaryOut)
def review_summary(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
) -> ReviewSummaryOut:
    return service.summary(db, user.id, now)


@router.get("/reviews/concepts", response_model=ConceptPage)
def review_concepts(
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
) -> ConceptPage:
    return service.concepts(db, user.id, now, limit=limit, cursor=cursor)


@router.post(
    "/review-sessions",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        200: {"description": "Today's open session was resumed", "model": SessionResponse},
        409: {"description": "Nothing is due (NOTHING_DUE)"},
    },
)
def start_session(
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
) -> SessionResponse:
    result, created = service.start_session(db, user.id, now)
    if not created:
        response.status_code = status.HTTP_200_OK
    return result


@router.get(
    "/review-sessions/{session_id}", response_model=SessionResponse, responses=SESSION_NOT_FOUND
)
def get_session(
    session_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SessionResponse:
    return service.get_session(db, user.id, session_id)


@router.post(
    "/review-sessions/{session_id}/items/{item_id}/answer",
    response_model=ReviewAnswerResponse,
    status_code=status.HTTP_201_CREATED,
    responses={**SESSION_NOT_FOUND, 200: {"description": "Replay of a stored answer"}},
)
def answer_item(
    response: Response,
    session_id: uuid.UUID,
    item_id: uuid.UUID,
    body: ReviewAnswerIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
) -> ReviewAnswerResponse:
    result, created = service.answer_item(
        db,
        user.id,
        session_id,
        item_id,
        selected=body.selected_option_ids,
        guessed=body.guessed,
        now=now,
    )
    if not created:
        response.status_code = status.HTTP_200_OK
    return result


@router.post(
    "/review-sessions/{session_id}/end", response_model=SessionResponse, responses=SESSION_NOT_FOUND
)
def end_session(
    session_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
) -> SessionResponse:
    return service.end_session(db, user.id, session_id, now)
