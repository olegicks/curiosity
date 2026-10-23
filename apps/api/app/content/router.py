"""/v1/subjects and /v1/lessons (docs/spec/05 §5.4)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.auth.models import User
from app.content import service
from app.content.schemas import LessonDetailOut, LessonPage, SubjectsOut
from app.core.db import get_db

router = APIRouter(tags=["content"])


@router.get("/subjects", response_model=SubjectsOut)
def list_subjects(
    _: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> SubjectsOut:
    return service.list_subjects(db)


@router.get("/lessons", response_model=LessonPage)
def list_lessons(
    subject: Annotated[str | None, Query(max_length=60)] = None,
    topic: Annotated[str | None, Query(max_length=60)] = None,
    progress: Annotated[service.ProgressFilter | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LessonPage:
    return service.list_lessons(
        db, user.id, subject=subject, topic=topic, progress=progress, limit=limit, cursor=cursor
    )


@router.get(
    "/lessons/{slug}",
    response_model=LessonDetailOut,
    responses={404: {"description": "Unknown, draft or retired lesson (LESSON_NOT_FOUND)"}},
)
def get_lesson(
    slug: Annotated[str, Path(max_length=60)],
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LessonDetailOut:
    return service.get_lesson_detail(db, user.id, slug)
