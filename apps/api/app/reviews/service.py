"""Due reviews, review sessions and answering review items (docs/spec/07 §7.3.6).

Each public function is one transaction. Lock order: session item -> review
state -> progress, matching the learning module.
"""

import math
import random
import uuid
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import Select, exists, func, select, tuple_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.content import service as content
from app.content.models import AnswerOption, Lesson, LessonVersion, Question
from app.content.schemas import OptionOut, QuestionOut
from app.core.clock import to_local_date
from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.core.pagination import InvalidCursorError, decode_cursor, encode_cursor
from app.learning.grading import is_correct, selection_problem
from app.learning.models import UserLessonProgress
from app.learning.schemas import OptionFeedbackOut
from app.reviews.models import ReviewEvent, ReviewSession, ReviewSessionItem, ReviewState
from app.reviews.scheduler import ReviewSchedule, Sm2Scheduler, mastery_stage
from app.reviews.schemas import (
    ConceptOut,
    ConceptPage,
    LessonRef,
    ReviewAnswerResponse,
    ReviewAnswerResult,
    ReviewSummaryOut,
    ScheduleOut,
    SessionItemOut,
    SessionOut,
    SessionProgressOut,
    SessionResponse,
    SessionSummaryOut,
    StageAdvanceOut,
    StageChangeOut,
)
from app.users.service import get_preferences

SESSION_MAX_ITEMS = 20
MINUTES_PER_ITEM = 0.5
REVIEWABLE_STATUSES = ("published", "retired")

scheduler = Sm2Scheduler()


class NothingDueError(ConflictError):
    code = "NOTHING_DUE"
    message = "No reviews are due."


class SessionNotFoundError(NotFoundError):
    code = "SESSION_NOT_FOUND"
    message = "Review session not found."


class ItemNotFoundError(NotFoundError):
    code = "ITEM_NOT_FOUND"
    message = "Review item not found."


class SessionNotOpenError(ConflictError):
    code = "SESSION_NOT_OPEN"
    message = "This review session is no longer open."


class SelectionError(ValidationError):
    message = "Invalid answer selection."


def local_today(db: Session, user_id: uuid.UUID, now: datetime) -> date:
    return to_local_date(now, get_preferences(db, user_id).timezone)


# --- due queries ------------------------------------------------------------------------


def _reviewable(user_id: uuid.UUID) -> Select[ReviewState, Lesson, LessonVersion]:
    """Review states whose lesson is still reviewable and has recall questions."""
    has_recall = exists().where(
        Question.lesson_version_id == LessonVersion.id, Question.role == "recall"
    )
    return (
        select(ReviewState, Lesson, LessonVersion)
        .join(Lesson, Lesson.id == ReviewState.lesson_id)
        .join(LessonVersion, LessonVersion.id == Lesson.current_version_id)
        .where(
            ReviewState.user_id == user_id,
            Lesson.status.in_(REVIEWABLE_STATUSES),
            has_recall,
        )
    )


def due_review_states(
    db: Session, user_id: uuid.UUID, today: date, *, limit: int | None = None
) -> list[tuple[ReviewState, Lesson, LessonVersion]]:
    """The single source for 'what is due', shared by the summary and session creation."""
    stmt = (
        _reviewable(user_id)
        .join(
            UserLessonProgress,
            (UserLessonProgress.user_id == ReviewState.user_id)
            & (UserLessonProgress.lesson_id == ReviewState.lesson_id),
        )
        .where(ReviewState.due_on <= today)
        .order_by(ReviewState.due_on, UserLessonProgress.first_completed_at, ReviewState.lesson_id)
    )
    if limit is not None:
        stmt = stmt.limit(limit)
    return [(state, lesson, version) for state, lesson, version in db.execute(stmt)]


def summary(db: Session, user_id: uuid.UUID, now: datetime) -> ReviewSummaryOut:
    today = local_today(db, user_id, now)
    due = due_review_states(db, user_id, today)
    reviewable = _reviewable(user_id).subquery()
    in_review = db.scalar(select(func.count()).select_from(reviewable)) or 0
    next_due = db.scalar(select(func.min(reviewable.c.due_on)).where(reviewable.c.due_on > today))
    open_session = _open_session(db, user_id)
    return ReviewSummaryOut(
        due_count=len(due),
        next_due_on=next_due,
        in_review_count=in_review,
        open_session_id=open_session.id
        if open_session is not None and open_session.local_date == today
        else None,
        estimated_minutes=math.ceil(min(len(due), SESSION_MAX_ITEMS) * MINUTES_PER_ITEM),
    )


def concepts(
    db: Session, user_id: uuid.UUID, now: datetime, *, limit: int, cursor: str | None
) -> ConceptPage:
    today = local_today(db, user_id, now)
    stmt = _reviewable(user_id).order_by(ReviewState.due_on, ReviewState.lesson_id)
    if cursor is not None:
        key = decode_cursor(cursor)
        try:
            after = (date.fromisoformat(str(key[0])), uuid.UUID(str(key[1])))
        except (IndexError, ValueError):
            raise InvalidCursorError(details=[{"field": "cursor", "issue": "malformed"}]) from None
        stmt = stmt.where(tuple_(ReviewState.due_on, ReviewState.lesson_id) > after)
    rows = [(s, lesson, v) for s, lesson, v in db.execute(stmt.limit(limit + 1))]
    page = rows[:limit]
    items = [
        ConceptOut(
            lesson=LessonRef(slug=lesson.slug, title=version.title),
            mastery_stage=mastery_stage(completed=True, repetitions=state.repetitions),
            due_on=state.due_on,
            is_due=state.due_on <= today,
        )
        for state, lesson, version in page
    ]
    next_cursor = None
    if len(rows) > limit:
        last = page[-1][0]
        next_cursor = encode_cursor([last.due_on.isoformat(), str(last.lesson_id)])
    return ConceptPage(items=items, next_cursor=next_cursor)


# --- sessions ---------------------------------------------------------------------------------


def _open_session(db: Session, user_id: uuid.UUID) -> ReviewSession | None:
    return db.scalar(
        select(ReviewSession).where(
            ReviewSession.user_id == user_id, ReviewSession.status == "open"
        )
    )


def _choose_question(
    db: Session, session_id: uuid.UUID, state: ReviewState, version_id: uuid.UUID
) -> uuid.UUID:
    """Uniformly random recall question, avoiding the one shown last time (spec 07 §7.3.6)."""
    pool = list(
        db.scalars(
            select(Question.id)
            .where(Question.lesson_version_id == version_id, Question.role == "recall")
            .order_by(Question.position)
        )
    )
    if len(pool) > 1 and state.last_question_id in pool:
        pool.remove(state.last_question_id)
    rng = random.Random(f"{session_id}:{state.lesson_id}")  # noqa: S311 - not security
    return rng.choice(pool)


def start_session(db: Session, user_id: uuid.UUID, now: datetime) -> tuple[SessionResponse, bool]:
    """Return today's open session or create one from the due items. (response, created)"""
    today = local_today(db, user_id, now)
    existing = _open_session(db, user_id)
    if existing is not None and existing.local_date == today:
        return _session_response(db, existing, resumed=True), False
    if existing is not None:  # yesterday's session; its unanswered items are still due
        existing.status = "expired"
        existing.ended_at = now
        db.flush()

    due = due_review_states(db, user_id, today, limit=SESSION_MAX_ITEMS)
    if not due:
        db.commit()
        upcoming = summary(db, user_id, now).next_due_on
        raise NothingDueError(details=[{"next_due_on": upcoming.isoformat() if upcoming else None}])

    session = ReviewSession(user_id=user_id, local_date=today, status="open", item_count=len(due))
    try:
        with db.begin_nested():
            db.add(session)
            db.flush()
            for position, (state, _, version) in enumerate(due, start=1):
                db.add(
                    ReviewSessionItem(
                        session_id=session.id,
                        lesson_id=state.lesson_id,
                        question_id=_choose_question(db, session.id, state, version.id),
                        position=position,
                    )
                )
    except IntegrityError:
        db.commit()  # a concurrent request created today's session first
        winner = _open_session(db, user_id)
        if winner is None:
            raise
        return _session_response(db, winner, resumed=True), False
    db.commit()
    return _session_response(db, session, resumed=False), True


def _get_session(db: Session, user_id: uuid.UUID, session_id: uuid.UUID) -> ReviewSession:
    session = db.scalar(
        select(ReviewSession).where(
            ReviewSession.id == session_id, ReviewSession.user_id == user_id
        )
    )
    if session is None:
        raise SessionNotFoundError
    return session


def get_session(db: Session, user_id: uuid.UUID, session_id: uuid.UUID) -> SessionResponse:
    session = _get_session(db, user_id, session_id)
    return _session_response(db, session, resumed=session.status == "open")


def end_session(
    db: Session, user_id: uuid.UUID, session_id: uuid.UUID, now: datetime
) -> SessionResponse:
    """End early; unanswered items simply stay due. Idempotent for closed sessions."""
    session = _get_session(db, user_id, session_id)
    if session.status == "open":
        session.status = "ended_early"
        session.ended_at = now
    response = _session_response(db, session, resumed=False)
    db.commit()
    return response


# --- answering ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class _ItemQuestion:
    question: Question
    options: list[AnswerOption]


def _item_question(db: Session, item: ReviewSessionItem) -> _ItemQuestion:
    question = db.get(Question, item.question_id)
    assert question is not None  # noqa: S101 - FK guarantees it
    options = list(
        db.scalars(
            select(AnswerOption)
            .where(AnswerOption.question_id == question.id)
            .order_by(AnswerOption.position)
        )
    )
    ordered = content.shuffled(
        options, seed=str(item.id), question_id=question.id, enabled=question.shuffle
    )
    return _ItemQuestion(question, ordered)


def _result_from_event(iq: _ItemQuestion, event: ReviewEvent) -> ReviewAnswerResult:
    return ReviewAnswerResult(
        is_correct=event.is_correct,
        quality=event.quality,
        selected_option_ids=list(event.selected_option_ids),
        correct_option_ids=[o.id for o in iq.options if o.is_correct],
        option_feedback=[
            OptionFeedbackOut(option_id=o.id, is_correct=o.is_correct, feedback=o.feedback)
            for o in iq.options
        ],
        explanation=iq.question.explanation,
        schedule=ScheduleOut(
            previous_interval_days=event.interval_before,
            next_interval_days=event.interval_after,
            next_due_on=event.due_on_after,
        ),
        mastery_stage=StageChangeOut(
            before=mastery_stage(completed=True, repetitions=event.reps_before),
            after=mastery_stage(completed=True, repetitions=event.reps_after),
        ),
    )


def answer_item(
    db: Session,
    user_id: uuid.UUID,
    session_id: uuid.UUID,
    item_id: uuid.UUID,
    *,
    selected: list[uuid.UUID],
    guessed: bool,
    now: datetime,
) -> tuple[ReviewAnswerResponse, bool]:
    session = _get_session(db, user_id, session_id)
    item = db.scalar(
        select(ReviewSessionItem)
        .where(ReviewSessionItem.id == item_id, ReviewSessionItem.session_id == session.id)
        .with_for_update()
    )
    if item is None:
        raise ItemNotFoundError
    iq = _item_question(db, item)
    stored = db.scalar(select(ReviewEvent).where(ReviewEvent.session_item_id == item.id))
    if stored is not None:
        response = _answer_response(db, session, _result_from_event(iq, stored), replayed=True)
        db.commit()
        return response, False
    if session.status != "open":
        raise SessionNotOpenError
    problem = selection_problem(iq.question.type, selected, [o.id for o in iq.options])
    if problem:
        raise SelectionError(
            code=problem, details=[{"field": "selected_option_ids", "issue": problem.lower()}]
        )

    today = local_today(db, user_id, now)
    state = db.scalar(
        select(ReviewState)
        .where(ReviewState.user_id == user_id, ReviewState.lesson_id == item.lesson_id)
        .with_for_update()
    )
    progress = db.scalar(
        select(UserLessonProgress)
        .where(
            UserLessonProgress.user_id == user_id,
            UserLessonProgress.lesson_id == item.lesson_id,
        )
        .with_for_update()
    )
    if state is None or progress is None or progress.first_completed_at is None:
        raise ItemNotFoundError  # cannot happen for items built from review states

    correct = is_correct(selected, [o.id for o in iq.options if o.is_correct])
    quality = scheduler.grade(is_correct=correct, guessed=guessed)
    before = ReviewSchedule(
        ease_factor=state.ease_factor,
        interval_days=state.interval_days,
        repetitions=state.repetitions,
        lapses=state.lapses,
        due_on=state.due_on,
    )
    after = scheduler.next_state(before, quality, today)

    timezone = get_preferences(db, user_id).timezone
    last_seen = state.last_reviewed_at or progress.first_completed_at
    previous_reviews = db.scalar(
        select(func.count())
        .select_from(ReviewEvent)
        .where(ReviewEvent.user_id == user_id, ReviewEvent.lesson_id == item.lesson_id)
    )
    event = ReviewEvent(
        user_id=user_id,
        session_item_id=item.id,
        lesson_id=item.lesson_id,
        question_id=item.question_id,
        selected_option_ids=selected,
        is_correct=correct,
        guessed=guessed,
        quality=quality,
        scheduler_version=scheduler.version,
        ef_before=before.ease_factor,
        ef_after=after.ease_factor,
        interval_before=before.interval_days,
        interval_after=after.interval_days,
        reps_before=before.repetitions,
        reps_after=after.repetitions,
        due_on_before=before.due_on,
        due_on_after=after.due_on,
        days_since_last_review=(today - to_local_date(last_seen, timezone)).days,
        review_number=(previous_reviews or 0) + 1,
        local_date=today,
        answered_at=now,
    )
    db.add(event)

    state.ease_factor = after.ease_factor
    state.interval_days = after.interval_days
    state.repetitions = after.repetitions
    state.lapses = after.lapses
    state.due_on = after.due_on
    state.scheduler_version = scheduler.version
    state.last_reviewed_at = now
    state.last_question_id = item.question_id

    # milestones are monotonic: set once, never cleared (spec 07 §7.2)
    if quality >= 3 and progress.first_recalled_at is None:
        progress.first_recalled_at = now
    if after.repetitions >= 2 and progress.first_understood_at is None:
        progress.first_understood_at = now
    progress.last_activity_at = now

    item.answered_at = now
    db.flush()
    unanswered = db.scalar(
        select(func.count())
        .select_from(ReviewSessionItem)
        .where(ReviewSessionItem.session_id == session.id, ReviewSessionItem.answered_at.is_(None))
    )
    if unanswered == 0:
        session.status = "completed"
        session.completed_at = now
    response = _answer_response(db, session, _result_from_event(iq, event), replayed=False)
    db.commit()
    return response, True


# --- views -------------------------------------------------------------------------------------


def _items_with_events(
    db: Session, session: ReviewSession
) -> list[tuple[ReviewSessionItem, ReviewEvent | None]]:
    items = db.scalars(
        select(ReviewSessionItem)
        .where(ReviewSessionItem.session_id == session.id)
        .order_by(ReviewSessionItem.position)
    ).all()
    events = {
        e.session_item_id: e
        for e in db.scalars(
            select(ReviewEvent).where(ReviewEvent.session_item_id.in_([i.id for i in items]))
        )
    }
    return [(item, events.get(item.id)) for item in items]


def _lesson_refs(db: Session, lesson_ids: list[uuid.UUID]) -> dict[uuid.UUID, LessonRef]:
    rows = db.execute(
        select(Lesson.id, Lesson.slug, LessonVersion.title)
        .join(LessonVersion, LessonVersion.id == Lesson.current_version_id)
        .where(Lesson.id.in_(lesson_ids))
    )
    return {lesson_id: LessonRef(slug=slug, title=title) for lesson_id, slug, title in rows}


def _summary(db: Session, session: ReviewSession) -> SessionSummaryOut:
    pairs = [(i, e) for i, e in _items_with_events(db, session) if e is not None]
    refs = _lesson_refs(db, [i.lesson_id for i, _ in pairs])
    advanced = []
    for item, event in pairs:
        before = mastery_stage(completed=True, repetitions=event.reps_before)
        after = mastery_stage(completed=True, repetitions=event.reps_after)
        if after > before:
            advanced.append(
                StageAdvanceOut(slug=refs[item.lesson_id].slug, from_stage=before, to_stage=after)
            )
    return SessionSummaryOut(
        correct=sum(e.is_correct for _, e in pairs),
        total=len(pairs),
        advanced=advanced,
        to_revisit=[refs[i.lesson_id] for i, e in pairs if not e.is_correct],
    )


def _session_response(db: Session, session: ReviewSession, *, resumed: bool) -> SessionResponse:
    pairs = _items_with_events(db, session)
    refs = _lesson_refs(db, [i.lesson_id for i, _ in pairs])
    items = []
    for item, event in pairs:
        iq = _item_question(db, item)
        items.append(
            SessionItemOut(
                id=item.id,
                position=item.position,
                lesson=refs[item.lesson_id],
                question=QuestionOut(
                    id=iq.question.id,
                    type=iq.question.type,
                    prompt=iq.question.prompt,
                    options=[OptionOut(id=o.id, text=o.text) for o in iq.options],
                ),
                result=_result_from_event(iq, event) if event else None,
            )
        )
    return SessionResponse(
        session=SessionOut(
            id=session.id,
            status=session.status,
            local_date=session.local_date,
            item_count=session.item_count,
            answered_count=sum(e is not None for _, e in pairs),
            items=items,
        ),
        summary=None if session.status == "open" else _summary(db, session),
        resumed=resumed,
    )


def _answer_response(
    db: Session, session: ReviewSession, result: ReviewAnswerResult, *, replayed: bool
) -> ReviewAnswerResponse:
    answered = db.scalar(
        select(func.count())
        .select_from(ReviewSessionItem)
        .where(
            ReviewSessionItem.session_id == session.id, ReviewSessionItem.answered_at.is_not(None)
        )
    )
    return ReviewAnswerResponse(
        result=result,
        session=SessionProgressOut(
            answered_count=answered or 0,
            item_count=session.item_count,
            status=session.status,
        ),
        session_summary=_summary(db, session) if session.status == "completed" else None,
        replayed=replayed,
    )
