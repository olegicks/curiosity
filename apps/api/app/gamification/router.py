"""/v1/progress and /v1/achievements (docs/spec/05 §5.7)."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user, get_now
from app.auth.models import User
from app.content.models import Lesson, Subject, Topic
from app.core.db import get_db
from app.gamification import service
from app.gamification.schemas import (
    AccuracyOut,
    AchievementsOut,
    LessonCountsOut,
    ProgressOut,
    ReviewTotalsOut,
    TopicProgressOut,
    XpTotalsOut,
)
from app.learning.models import UserLessonProgress
from app.learning.progress import progress_briefs
from app.reviews import service as reviews
from app.reviews.models import ReviewEvent

router = APIRouter(tags=["progress"])

RECENT_ACCURACY_WINDOW = 20


def _recall_accuracy(db: Session, user_id: uuid.UUID) -> AccuracyOut:
    recent = db.scalars(
        select(ReviewEvent.is_correct)
        .where(ReviewEvent.user_id == user_id)
        .order_by(ReviewEvent.answered_at.desc(), ReviewEvent.id.desc())
        .limit(RECENT_ACCURACY_WINDOW)
    ).all()
    return AccuracyOut(correct=sum(recent), total=len(recent))


@router.get("/progress", response_model=ProgressOut)
def get_progress(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
) -> ProgressOut:
    published = list(
        db.execute(
            select(Lesson.id, Topic.id, Topic.slug, Topic.title)
            .join(Topic, Topic.id == Lesson.topic_id)
            .join(Subject, Subject.id == Topic.subject_id)
            .where(Lesson.status == "published", Subject.is_published.is_(True))
            .order_by(Subject.position, Topic.position)
        )
    )
    lesson_ids = [lesson_id for lesson_id, *_ in published]
    briefs = progress_briefs(db, user.id, lesson_ids)
    by_stage = {str(stage): 0 for stage in range(1, 5)}
    for brief in briefs.values():
        if brief.mastery_stage:
            by_stage[str(brief.mastery_stage)] += 1

    topics: dict[uuid.UUID, TopicProgressOut] = {}
    for lesson_id, topic_id, slug, title in published:
        topic = topics.setdefault(
            topic_id, TopicProgressOut(slug=slug, title=title, total=0, completed=0)
        )
        topic.total += 1
        topic.completed += briefs[lesson_id].completed_at is not None

    started = db.scalar(
        select(func.count())
        .select_from(UserLessonProgress)
        .where(UserLessonProgress.user_id == user.id, UserLessonProgress.lesson_id.in_(lesson_ids))
    )
    today = reviews.local_today(db, user.id, now)
    xp = service.xp_summary(db, user.id, today)
    due = reviews.summary(db, user.id, now)
    return ProgressOut(
        lessons=LessonCountsOut(
            total=len(lesson_ids),
            started=started or 0,
            completed=sum(b.completed_at is not None for b in briefs.values()),
            by_stage=by_stage,
        ),
        by_topic=list(topics.values()),
        xp=XpTotalsOut(total=xp.total, today=xp.today, goal=xp.goal),
        streak=service.streak_out(db, user.id, today),
        recall_accuracy=_recall_accuracy(db, user.id),
        reviews=ReviewTotalsOut(due_count=due.due_count, next_due_on=due.next_due_on),
    )


@router.get("/achievements", response_model=AchievementsOut)
def get_achievements(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> AchievementsOut:
    return AchievementsOut(items=service.achievements(db, user.id))
