"""Discover home screen and lesson recommendations (docs/spec/02 §2.5, 07 §7.8)."""

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.content import service as content
from app.content.models import Lesson
from app.content.schemas import LessonSummary
from app.gamification import service as gamification
from app.learning.models import LessonAttempt, UserLessonProgress
from app.learning.progress import progress_briefs
from app.learning.recommendations import (
    RECOMMENDED_COUNT,
    LessonInfo,
    next_after_completion,
    rank_lessons,
)
from app.learning.schemas import (
    DiscoverOut,
    DiscoverProgressOut,
    DiscoverXpOut,
    PrimaryActionOut,
    ReviewActionOut,
)
from app.reviews import service as reviews
from app.users.service import interest_topic_slugs


def _completed_slugs(db: Session, user_id: uuid.UUID) -> set[str]:
    return set(
        db.scalars(
            select(Lesson.slug)
            .join(UserLessonProgress, UserLessonProgress.lesson_id == Lesson.id)
            .where(
                UserLessonProgress.user_id == user_id,
                UserLessonProgress.first_completed_at.is_not(None),
            )
        )
    )


def _last_completed_lesson(db: Session, user_id: uuid.UUID) -> uuid.UUID | None:
    return db.scalar(
        select(LessonAttempt.lesson_id)
        .where(LessonAttempt.user_id == user_id, LessonAttempt.status == "completed")
        .order_by(LessonAttempt.completed_at.desc(), LessonAttempt.id.desc())
        .limit(1)
    )


def _lesson_infos(infos: list[content.PublishedLessonInfo]) -> list[LessonInfo]:
    return [LessonInfo(i.slug, i.topic, i.prerequisites) for i in infos]


def _summaries_in_order(db: Session, user_id: uuid.UUID, slugs: list[str]) -> list[LessonSummary]:
    by_slug = {s.slug: s for s in content.lesson_summaries(db, user_id, slugs)}
    return [by_slug[slug] for slug in slugs if slug in by_slug]


def ranked_lessons(db: Session, user_id: uuid.UUID) -> list[str]:
    last = _last_completed_lesson(db, user_id)
    return rank_lessons(
        _lesson_infos(content.published_lesson_infos(db)),
        completed=_completed_slugs(db, user_id),
        interests=interest_topic_slugs(db, user_id),
        boost_related=content.related_published_slugs(db, last) if last else [],
    )


def next_lesson_after(
    db: Session, user_id: uuid.UUID, lesson_id: uuid.UUID
) -> LessonSummary | None:
    """The "Next" lesson on the completion screen (spec 07 §7.8 rule 6)."""
    slug = next_after_completion(
        _lesson_infos(content.published_lesson_infos(db)),
        completed=_completed_slugs(db, user_id),
        interests=interest_topic_slugs(db, user_id),
        related=content.related_published_slugs(db, lesson_id),
    )
    return _summaries_in_order(db, user_id, [slug])[0] if slug else None


def _open_attempt(db: Session, user_id: uuid.UUID) -> tuple[uuid.UUID, str] | None:
    """Most recently started open attempt on a published lesson."""
    row = db.execute(
        select(LessonAttempt.id, Lesson.slug)
        .join(Lesson, Lesson.id == LessonAttempt.lesson_id)
        .where(
            LessonAttempt.user_id == user_id,
            LessonAttempt.status == "in_progress",
            Lesson.status == "published",
        )
        .order_by(LessonAttempt.started_at.desc(), LessonAttempt.id.desc())
        .limit(1)
    ).first()
    return (row[0], row[1]) if row else None


def discover(db: Session, user_id: uuid.UUID, now: datetime) -> DiscoverOut:
    today = reviews.local_today(db, user_id, now)
    due = reviews.summary(db, user_id, now)
    ranked = ranked_lessons(db, user_id)
    picks = _summaries_in_order(db, user_id, ranked[: RECOMMENDED_COUNT + 1])
    todays = picks[0] if picks else None
    open_attempt = _open_attempt(db, user_id)

    # Priority (spec 02 §2.5): reviews due > continue lesson > today's lesson > caught up
    if due.due_count > 0:
        primary = PrimaryActionOut(
            type="review",
            review=ReviewActionOut(
                due_count=due.due_count,
                estimated_minutes=due.estimated_minutes,
                open_session_id=due.open_session_id,
            ),
        )
    elif open_attempt is not None:
        attempt_id, slug = open_attempt
        primary = PrimaryActionOut(
            type="continue_lesson",
            lesson=_summaries_in_order(db, user_id, [slug])[0],
            attempt_id=attempt_id,
        )
    elif todays is not None:
        primary = PrimaryActionOut(type="start_lesson", lesson=todays)
    else:
        primary = PrimaryActionOut(type="caught_up", next_review_on=due.next_due_on)

    infos = content.published_lesson_infos(db)
    briefs = progress_briefs(db, user_id, [i.lesson_id for i in infos])
    xp = gamification.xp_summary(db, user_id, today)
    return DiscoverOut(
        local_date=today,
        primary_action=primary,
        todays_lesson=todays,
        recommended=picks[1:],
        progress=DiscoverProgressOut(
            lessons_total=len(infos),
            completed=sum(b.completed_at is not None for b in briefs.values()),
            understood=sum(b.mastery_stage >= 3 for b in briefs.values()),
        ),
        streak=gamification.streak_out(db, user_id, today),
        xp=DiscoverXpOut(today=xp.today, goal=xp.goal, total=xp.total),
        reviews_due=due.due_count,
    )
