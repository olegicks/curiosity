"""Idempotent, all-or-nothing import of validated content (docs/spec/03 §3.1)."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.content.loader import ContentSet, ContentValidationError, content_hash
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
from app.content.schema import LessonFile, LessonStatus


class ContentImportError(Exception):
    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__(f"{len(errors)} import error(s)")


@dataclass
class ImportSummary:
    created: list[str] = field(default_factory=list)
    new_versions: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    retired: list[str] = field(default_factory=list)
    missing_from_files: list[str] = field(default_factory=list)


def import_content(
    db: Session, content: ContentSet, *, now: datetime, allow_draft_overwrite: bool = False
) -> ImportSummary:
    """Write the content set in one transaction; nothing is written if anything fails."""
    if not content.ok:
        raise ContentValidationError(content.errors)
    errors: list[str] = []
    summary = ImportSummary()
    try:
        topic_ids = _upsert_subjects(db, content)
        source_ids = _upsert_sources(db, content)
        lesson_ids: dict[str, uuid.UUID] = {}
        for lesson_file in content.lessons:
            lesson = _upsert_lesson(
                db,
                lesson_file,
                topic_id=topic_ids[(lesson_file.subject, lesson_file.topic)],
                source_ids=source_ids,
                now=now,
                allow_draft_overwrite=allow_draft_overwrite,
                summary=summary,
                errors=errors,
            )
            if lesson is not None:
                lesson_ids[lesson_file.slug] = lesson.id
        if not errors:
            _rewrite_relations(db, content, lesson_ids)
            known = {lf.slug for lf in content.lessons}
            summary.missing_from_files = sorted(
                slug for slug in db.scalars(select(Lesson.slug)) if slug not in known
            )
    except Exception:
        db.rollback()
        raise
    if errors:
        db.rollback()
        raise ContentImportError(errors)
    db.commit()
    return summary


def _upsert_subjects(db: Session, content: ContentSet) -> dict[tuple[str, str], uuid.UUID]:
    topic_ids: dict[tuple[str, str], uuid.UUID] = {}
    for s in content.subjects:
        subject = db.scalar(select(Subject).where(Subject.slug == s.slug))
        if subject is None:
            subject = Subject(slug=s.slug)
            db.add(subject)
        subject.title, subject.description = s.title, s.description
        subject.position, subject.is_published = s.position, s.published
        db.flush()
        for t in s.topics:
            topic = db.scalar(
                select(Topic).where(Topic.subject_id == subject.id, Topic.slug == t.slug)
            )
            if topic is None:
                topic = Topic(subject_id=subject.id, slug=t.slug)
                db.add(topic)
            topic.title, topic.description, topic.position = t.title, t.description, t.position
            db.flush()
            topic_ids[(s.slug, t.slug)] = topic.id
    return topic_ids


def _upsert_sources(db: Session, content: ContentSet) -> dict[str, uuid.UUID]:
    ids: dict[str, uuid.UUID] = {}
    for src in content.sources.values():
        row = db.scalar(select(Source).where(Source.key == src.key))
        if row is None:
            row = Source(key=src.key)
            db.add(row)
        row.type, row.citation = src.type.value, src.citation
        row.doi, row.url, row.peer_reviewed = src.doi, src.url, src.peer_reviewed
        db.flush()
        ids[src.key] = row.id
    return ids


def _upsert_lesson(
    db: Session,
    lf: LessonFile,
    *,
    topic_id: uuid.UUID,
    source_ids: dict[str, uuid.UUID],
    now: datetime,
    allow_draft_overwrite: bool,
    summary: ImportSummary,
    errors: list[str],
) -> Lesson | None:
    lesson = db.get(Lesson, lf.id)
    by_slug = db.scalar(select(Lesson).where(Lesson.slug == lf.slug))
    if lesson is not None and lesson.slug != lf.slug:
        errors.append(f"{lf.slug}: lesson {lf.id} was imported as {lesson.slug!r}; slugs are fixed")
        return None
    if by_slug is not None and by_slug.id != lf.id:
        errors.append(f"{lf.slug}: slug already belongs to lesson {by_slug.id}")
        return None

    created = lesson is None
    if lesson is None:
        lesson = Lesson(id=lf.id, slug=lf.slug, status=LessonStatus.DRAFT.value)
        db.add(lesson)
    lesson.topic_id = topic_id
    lesson.position = lf.position
    db.flush()

    digest = content_hash(lf)
    version = db.scalar(
        select(LessonVersion).where(
            LessonVersion.lesson_id == lf.id, LessonVersion.version == lf.version
        )
    )
    if version is None:
        latest = db.scalar(
            select(LessonVersion.version)
            .where(LessonVersion.lesson_id == lf.id)
            .order_by(LessonVersion.version.desc())
            .limit(1)
        )
        if latest is not None and lf.version < latest:
            errors.append(f"{lf.slug}: version {lf.version} is older than imported {latest}")
            return None
        version = LessonVersion(lesson_id=lf.id, version=lf.version)
        db.add(version)
        _write_version_content(db, version, lf, digest, source_ids)
        if not created:
            summary.new_versions.append(f"{lf.slug} v{lf.version}")
    elif version.content_hash != digest:
        if version.published_at is None and allow_draft_overwrite:
            _write_version_content(db, version, lf, digest, source_ids, replace=True)
            summary.new_versions.append(f"{lf.slug} v{lf.version} (draft overwritten)")
        else:
            errors.append(f"{lf.slug}: content changed without a version bump (v{lf.version})")
            return None
    else:
        summary.unchanged.append(lf.slug)

    # editorial metadata is not part of the content hash; keep it current
    version.last_reviewed_on = lf.last_reviewed_on
    version.reviewers = list(lf.reviewers)

    if lf.status is LessonStatus.PUBLISHED:
        if version.published_at is None:
            version.published_at = now
        lesson.current_version_id = version.id
    elif lf.status is LessonStatus.RETIRED and lesson.status != LessonStatus.RETIRED.value:
        summary.retired.append(lf.slug)
    lesson.status = lf.status.value
    db.flush()
    if created:
        summary.created.append(lf.slug)
    return lesson


def _write_version_content(
    db: Session,
    version: LessonVersion,
    lf: LessonFile,
    digest: str,
    source_ids: dict[str, uuid.UUID],
    *,
    replace: bool = False,
) -> None:
    version.title, version.description = lf.title, lf.description
    version.learning_objective = lf.learning_objective
    version.estimated_minutes = lf.estimated_minutes
    version.evidence_status = lf.evidence_status.value
    version.body = {"steps": [step.model_dump(mode="json") for step in lf.steps]}
    version.content_hash = digest
    db.flush()
    if replace:
        db.execute(delete(Question).where(Question.lesson_version_id == version.id))
        db.execute(
            delete(LessonVersionSource).where(LessonVersionSource.lesson_version_id == version.id)
        )
    for q_pos, q in enumerate(lf.questions):
        question = Question(
            lesson_version_id=version.id,
            key=q.key,
            role=q.role.value,
            type=q.type.value,
            prompt=q.prompt,
            explanation=q.explanation,
            shuffle=q.shuffle,
            position=q_pos,
        )
        db.add(question)
        db.flush()
        for o_pos, opt in enumerate(q.options):
            db.add(
                AnswerOption(
                    question_id=question.id,
                    key=opt.key,
                    text=opt.text,
                    is_correct=opt.correct,
                    feedback=opt.feedback,
                    position=o_pos,
                )
            )
    for s_pos, ref in enumerate(lf.sources):
        db.add(
            LessonVersionSource(
                lesson_version_id=version.id,
                source_id=source_ids[ref.key],
                note=ref.note,
                position=s_pos,
            )
        )
    db.flush()


def _rewrite_relations(db: Session, content: ContentSet, lesson_ids: dict[str, uuid.UUID]) -> None:
    ids = list(lesson_ids.values())
    db.execute(delete(LessonRelation).where(LessonRelation.from_lesson_id.in_(ids)))
    for lf in content.lessons:
        for relation_type, slugs in (("related", lf.related), ("prerequisite", lf.prerequisites)):
            for position, slug in enumerate(slugs):
                db.add(
                    LessonRelation(
                        from_lesson_id=lesson_ids[lf.slug],
                        to_lesson_id=lesson_ids[slug],
                        relation_type=relation_type,
                        position=position,
                    )
                )
    db.flush()
