"""Read side of the content module: published subjects, lessons and lesson content."""

import random
import uuid
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import TypeAdapter
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.content.models import (
    AnswerOption,
    Lesson,
    LessonRelation,
    LessonVersion,
    LessonVersionSource,
    Question,
    Source,
    Subject,
    Topic,
)
from app.content.schemas import (
    EstimateOut,
    ImageOut,
    LessonContent,
    LessonDetail,
    LessonDetailOut,
    LessonPage,
    LessonSummary,
    OptionOut,
    QuestionOut,
    SourceOut,
    StepOut,
    SubjectOut,
    SubjectsOut,
    TopicOut,
    TopicRef,
)
from app.core.errors import NotFoundError
from app.core.pagination import InvalidCursorError, decode_cursor, encode_cursor
from app.learning.progress import ProgressBrief, progress_briefs

ProgressFilter = Literal["not_started", "in_progress", "completed"]
MEDIA_URL_PREFIX = "/media"

_PROGRESS_FILTERS: dict[str, set[str]] = {
    "not_started": {"not_started"},
    "in_progress": {"started"},
    "completed": {"completed", "recalled", "understood", "retained"},
}
_steps_adapter: TypeAdapter[list[StepOut]] = TypeAdapter(list[StepOut])


class LessonNotFoundError(NotFoundError):
    code = "LESSON_NOT_FOUND"
    message = "Lesson not found."


@dataclass(frozen=True)
class _Row:
    lesson: Lesson
    version: LessonVersion
    topic: Topic
    subject: Subject

    @property
    def sort_key(self) -> list[Any]:
        return [
            self.subject.position,
            self.topic.position,
            self.lesson.position,
            str(self.lesson.id),
        ]


def _published_rows(db: Session, *, slugs: list[str] | None = None) -> list[_Row]:
    stmt = (
        select(Lesson, LessonVersion, Topic, Subject)
        .join(LessonVersion, LessonVersion.id == Lesson.current_version_id)
        .join(Topic, Topic.id == Lesson.topic_id)
        .join(Subject, Subject.id == Topic.subject_id)
        .where(Lesson.status == "published", Subject.is_published.is_(True))
        .order_by(Subject.position, Topic.position, Lesson.position, Lesson.id)
    )
    if slugs is not None:
        stmt = stmt.where(Lesson.slug.in_(slugs))
    return [_Row(*row) for row in db.execute(stmt)]


def _summary(row: _Row, progress: ProgressBrief) -> LessonSummary:
    return LessonSummary(
        slug=row.lesson.slug,
        title=row.version.title,
        description=row.version.description,
        subject=TopicRef(slug=row.subject.slug, title=row.subject.title),
        topic=TopicRef(slug=row.topic.slug, title=row.topic.title),
        estimated_minutes=row.version.estimated_minutes,
        evidence_status=row.version.evidence_status,
        position=row.lesson.position,
        progress=progress,
    )


def _summaries(db: Session, user_id: uuid.UUID, rows: list[_Row]) -> list[LessonSummary]:
    progress = progress_briefs(db, user_id, [r.lesson.id for r in rows])
    return [_summary(r, progress[r.lesson.id]) for r in rows]


def list_subjects(db: Session) -> SubjectsOut:
    counts = {
        topic_id: count
        for topic_id, count in db.execute(
            select(Lesson.topic_id, func.count())
            .where(Lesson.status == "published")
            .group_by(Lesson.topic_id)
        )
    }
    subjects = db.scalars(
        select(Subject).where(Subject.is_published.is_(True)).order_by(Subject.position)
    ).all()
    items = []
    for subject in subjects:
        topics = db.scalars(
            select(Topic).where(Topic.subject_id == subject.id).order_by(Topic.position)
        ).all()
        items.append(
            SubjectOut(
                slug=subject.slug,
                title=subject.title,
                description=subject.description,
                topics=[
                    TopicOut(
                        slug=t.slug,
                        title=t.title,
                        description=t.description,
                        position=t.position,
                        lesson_count=counts.get(t.id, 0),
                    )
                    for t in topics
                ],
            )
        )
    return SubjectsOut(items=items)


def list_lessons(
    db: Session,
    user_id: uuid.UUID,
    *,
    subject: str | None = None,
    topic: str | None,
    progress: ProgressFilter | None,
    limit: int,
    cursor: str | None,
) -> LessonPage:
    """Filtering by progress needs per-user state, so the (small) published set is
    filtered in memory and paginated with a keyset cursor over the curated order."""
    rows = _published_rows(db)
    if subject is not None:
        rows = [r for r in rows if r.subject.slug == subject]
    if topic is not None:
        rows = [r for r in rows if r.topic.slug == topic]
    summaries = _summaries(db, user_id, rows)
    pairs = list(zip(rows, summaries, strict=True))
    if progress is not None:
        allowed = _PROGRESS_FILTERS[progress]
        pairs = [(r, s) for r, s in pairs if s.progress.status in allowed]
    if cursor is not None:
        after = decode_cursor(cursor)
        if len(after) != 4:
            raise InvalidCursorError(details=[{"field": "cursor", "issue": "malformed"}])
        pairs = [(r, s) for r, s in pairs if r.sort_key > after]
    page = pairs[:limit]
    next_cursor = encode_cursor(page[-1][0].sort_key) if len(pairs) > limit else None
    return LessonPage(items=[s for _, s in page], next_cursor=next_cursor)


@dataclass(frozen=True)
class PublishedLesson:
    lesson_id: uuid.UUID
    version_id: uuid.UUID


def get_published_lesson(db: Session, slug: str) -> PublishedLesson:
    rows = _published_rows(db, slugs=[slug])
    if not rows:
        raise LessonNotFoundError
    return PublishedLesson(lesson_id=rows[0].lesson.id, version_id=rows[0].version.id)


def related_published_slugs(db: Session, lesson_id: uuid.UUID) -> list[str]:
    """Published related lessons in curated order."""
    slugs = list(
        db.scalars(
            select(Lesson.slug)
            .join(LessonRelation, LessonRelation.to_lesson_id == Lesson.id)
            .where(
                LessonRelation.from_lesson_id == lesson_id,
                LessonRelation.relation_type == "related",
            )
            .order_by(LessonRelation.position)
        )
    )
    published = {r.lesson.slug for r in _published_rows(db, slugs=slugs)}
    return [slug for slug in slugs if slug in published]


def _related_summaries(
    db: Session, user_id: uuid.UUID, lesson_id: uuid.UUID
) -> list[LessonSummary]:
    slugs = related_published_slugs(db, lesson_id)
    rows = {r.lesson.slug: r for r in _published_rows(db, slugs=slugs)}
    return _summaries(db, user_id, [rows[s] for s in slugs])


def lesson_summaries(db: Session, user_id: uuid.UUID, slugs: list[str]) -> list[LessonSummary]:
    """Summaries of published lessons, in curated order."""
    return _summaries(db, user_id, _published_rows(db, slugs=slugs))


@dataclass(frozen=True)
class PublishedLessonInfo:
    lesson_id: uuid.UUID
    slug: str
    topic: str
    prerequisites: tuple[str, ...]  # published prerequisites only, in authored order


def published_lesson_infos(db: Session) -> list[PublishedLessonInfo]:
    """Published lessons in curated order with their (published) prerequisites."""
    rows = _published_rows(db)
    slug_by_id = {r.lesson.id: r.lesson.slug for r in rows}
    prerequisites: dict[uuid.UUID, list[str]] = {r.lesson.id: [] for r in rows}
    for from_id, to_id in db.execute(
        select(LessonRelation.from_lesson_id, LessonRelation.to_lesson_id)
        .where(
            LessonRelation.relation_type == "prerequisite",
            LessonRelation.from_lesson_id.in_(list(slug_by_id)),
        )
        .order_by(LessonRelation.position)
    ):
        if to_id in slug_by_id:
            prerequisites[from_id].append(slug_by_id[to_id])
    return [
        PublishedLessonInfo(
            lesson_id=r.lesson.id,
            slug=r.lesson.slug,
            topic=r.topic.slug,
            prerequisites=tuple(prerequisites[r.lesson.id]),
        )
        for r in rows
    ]


def get_lesson_detail(db: Session, user_id: uuid.UUID, slug: str) -> LessonDetailOut:
    rows = _published_rows(db, slugs=[slug])
    if not rows:
        raise LessonNotFoundError
    row = rows[0]
    summary = _summaries(db, user_id, [row])[0]
    related = _related_summaries(db, user_id, row.lesson.id)
    detail = LessonDetail(
        **summary.model_dump(),
        learning_objective=row.version.learning_objective,
        related=related,
    )
    return LessonDetailOut(
        lesson=detail, content=_lesson_content(db, row, related, shuffle_seed=str(user_id))
    )


def lesson_content_for_version(
    db: Session, user_id: uuid.UUID, version_id: uuid.UUID, *, shuffle_seed: str
) -> LessonContent:
    """Content of a specific (pinned) version, even if the lesson was revised or retired."""
    result = db.execute(
        select(Lesson, LessonVersion, Topic, Subject)
        .join(Lesson, Lesson.id == LessonVersion.lesson_id)
        .join(Topic, Topic.id == Lesson.topic_id)
        .join(Subject, Subject.id == Topic.subject_id)
        .where(LessonVersion.id == version_id)
    ).one()
    row = _Row(*result)
    return _lesson_content(
        db, row, _related_summaries(db, user_id, row.lesson.id), shuffle_seed=shuffle_seed
    )


def shuffled[T](items: list[T], *, seed: str, question_id: uuid.UUID, enabled: bool) -> list[T]:
    """Deterministic option order for a seed (attempt or user) and question."""
    ordered = list(items)
    if enabled:
        random.Random(f"{seed}:{question_id}").shuffle(ordered)  # noqa: S311 - not security
    return ordered


def _lesson_content(
    db: Session, row: _Row, related: list[LessonSummary], *, shuffle_seed: str
) -> LessonContent:
    version = row.version
    questions = db.scalars(
        select(Question)
        .where(Question.lesson_version_id == version.id, Question.role == "lesson")
        .order_by(Question.position)
    ).all()
    question_ids = {q.key: q.id for q in questions}
    options: dict[uuid.UUID, list[AnswerOption]] = {q.id: [] for q in questions}
    for option in db.scalars(
        select(AnswerOption)
        .where(AnswerOption.question_id.in_(list(options)))
        .order_by(AnswerOption.position)
    ):
        options[option.question_id].append(option)

    question_out = []
    for q in questions:
        opts = shuffled(options[q.id], seed=shuffle_seed, question_id=q.id, enabled=q.shuffle)
        question_out.append(
            QuestionOut(
                id=q.id,
                type=q.type,
                prompt=q.prompt,
                options=[OptionOut(id=o.id, text=o.text) for o in opts],
                estimate=EstimateOut(
                    min=q.estimate["min"],
                    max=q.estimate["max"],
                    step=q.estimate["step"],
                    unit=q.estimate["unit"],
                    anchor=q.estimate.get("anchor"),
                )
                if q.estimate
                else None,
            )
        )

    sources = db.execute(
        select(Source)
        .join(LessonVersionSource, LessonVersionSource.source_id == Source.id)
        .where(LessonVersionSource.lesson_version_id == version.id)
        .order_by(LessonVersionSource.position)
    ).scalars()

    return LessonContent(
        lesson_version_id=version.id,
        version=version.version,
        slug=row.lesson.slug,
        title=version.title,
        learning_objective=version.learning_objective,
        estimated_minutes=version.estimated_minutes,
        evidence_status=version.evidence_status,
        steps=_steps_adapter.validate_python(
            [_step_out(step, row.lesson.slug, question_ids) for step in version.body["steps"]]
        ),
        questions=question_out,
        sources=[SourceOut(key=s.key, citation=s.citation, url=s.url, doi=s.doi) for s in sources],
        related=related,
    )


def _step_out(
    step: dict[str, Any], slug: str, question_ids: dict[str, uuid.UUID]
) -> dict[str, Any]:
    if step["type"] == "question":
        return {"type": "question", "question_id": question_ids[step["question_key"]]}
    out = dict(step)
    if step["type"] in {"hook", "explanation"}:
        image = step.get("image")
        out["image"] = (
            ImageOut(
                url=f"{MEDIA_URL_PREFIX}/{slug}/{image['file']}",
                alt=image["alt"],
                caption=image.get("caption"),
            )
            if image
            else None
        )
    return out


def resolve_topic_ids(db: Session, slugs: list[str]) -> dict[str, uuid.UUID]:
    """Map topic slugs (in published subjects) to ids; unknown slugs are omitted."""
    rows = db.execute(
        select(Topic.slug, Topic.id)
        .join(Subject, Subject.id == Topic.subject_id)
        .where(Topic.slug.in_(slugs), Subject.is_published.is_(True))
    )
    return {slug: topic_id for slug, topic_id in rows}
