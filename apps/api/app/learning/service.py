"""Lesson attempt lifecycle: start/resume, server-side grading, completion
(docs/spec/05 §5.5, 07 §7.2-7.3, 04 §4.9).

Each public function is one transaction. Rows are locked in the fixed order
attempt -> progress -> review state to avoid deadlocks.
"""

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.content import service as content
from app.content.models import AnswerOption, Question
from app.core.clock import to_local_date
from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.gamification import service as gamification
from app.learning import discover
from app.learning.grading import (
    estimate_correct,
    estimate_problem,
    is_correct,
    selection_problem,
)
from app.learning.models import LessonAttempt, LessonAttemptAnswer, UserLessonProgress
from app.learning.schemas import (
    AnswerResponse,
    AnswerResult,
    AttemptOut,
    AttemptResponse,
    CompletedAttemptOut,
    CompletionResponse,
    EstimateResultOut,
    OptionFeedbackOut,
)
from app.reviews.models import ReviewState
from app.reviews.scheduler import Sm2Scheduler
from app.users.service import get_preferences

scheduler = Sm2Scheduler()


class AttemptNotFoundError(NotFoundError):
    code = "ATTEMPT_NOT_FOUND"
    message = "Attempt not found."


class AttemptNotOpenError(ConflictError):
    code = "ATTEMPT_NOT_OPEN"
    message = "This attempt is no longer open."


class AttemptIncompleteError(ConflictError):
    code = "ATTEMPT_INCOMPLETE"
    message = "Answer every question before completing the lesson."


class QuestionNotInAttemptError(ValidationError):
    code = "QUESTION_NOT_IN_ATTEMPT"
    message = "This question is not part of the lesson attempt."


class SelectionError(ValidationError):
    message = "Invalid answer selection."


@dataclass(frozen=True)
class _LessonQuestion:
    question: Question
    options: list[AnswerOption]  # authored order


def _lesson_questions(db: Session, version_id: uuid.UUID) -> dict[uuid.UUID, _LessonQuestion]:
    questions = db.scalars(
        select(Question)
        .where(Question.lesson_version_id == version_id, Question.role == "lesson")
        .order_by(Question.position)
    ).all()
    options: dict[uuid.UUID, list[AnswerOption]] = {q.id: [] for q in questions}
    for option in db.scalars(
        select(AnswerOption)
        .where(AnswerOption.question_id.in_(list(options)))
        .order_by(AnswerOption.position)
    ):
        options[option.question_id].append(option)
    return {q.id: _LessonQuestion(q, options[q.id]) for q in questions}


def _answer_result(
    attempt: LessonAttempt, lq: _LessonQuestion, answer: LessonAttemptAnswer
) -> AnswerResult:
    ordered = content.shuffled(
        lq.options, seed=str(attempt.id), question_id=lq.question.id, enabled=lq.question.shuffle
    )
    return AnswerResult(
        question_id=lq.question.id,
        is_correct=answer.is_correct,
        selected_option_ids=list(answer.selected_option_ids),
        correct_option_ids=[o.id for o in ordered if o.is_correct],
        option_feedback=[
            OptionFeedbackOut(option_id=o.id, is_correct=o.is_correct, feedback=o.feedback)
            for o in ordered
        ],
        explanation=lq.question.explanation,
        estimate=EstimateResultOut(
            value=answer.value,
            answer=lq.question.estimate["answer"],
            tolerance=lq.question.estimate["tolerance"],
            unit=lq.question.estimate["unit"],
        )
        if lq.question.estimate and answer.value is not None
        else None,
    )


def get_owned_attempt(
    db: Session, user_id: uuid.UUID, attempt_id: uuid.UUID, *, lock: bool = False
) -> LessonAttempt:
    stmt = select(LessonAttempt).where(
        LessonAttempt.id == attempt_id, LessonAttempt.user_id == user_id
    )
    attempt = db.scalar(stmt.with_for_update() if lock else stmt)
    if attempt is None:
        raise AttemptNotFoundError
    return attempt


def _progress(db: Session, user_id: uuid.UUID, lesson_id: uuid.UUID) -> UserLessonProgress | None:
    return db.get(UserLessonProgress, (user_id, lesson_id))


def _attempt_response(
    db: Session, user_id: uuid.UUID, attempt: LessonAttempt, *, resumed: bool
) -> AttemptResponse:
    questions = _lesson_questions(db, attempt.lesson_version_id)
    answers = db.scalars(
        select(LessonAttemptAnswer)
        .where(LessonAttemptAnswer.attempt_id == attempt.id)
        .order_by(LessonAttemptAnswer.answered_at, LessonAttemptAnswer.id)
    ).all()
    progress = _progress(db, user_id, attempt.lesson_id)
    first_completed = progress.first_completed_at if progress else None
    is_revisit = (
        first_completed is not None
        and first_completed <= attempt.started_at
        and not attempt.is_first_completion
    )
    return AttemptResponse(
        attempt=AttemptOut(
            id=attempt.id,
            status=attempt.status,
            lesson_version_id=attempt.lesson_version_id,
            started_at=attempt.started_at,
            answers=[_answer_result(attempt, questions[a.question_id], a) for a in answers],
            is_revisit=is_revisit,
        ),
        content=content.lesson_content_for_version(
            db, user_id, attempt.lesson_version_id, shuffle_seed=str(attempt.id)
        ),
        resumed=resumed,
    )


def _open_attempt(db: Session, user_id: uuid.UUID, lesson_id: uuid.UUID) -> LessonAttempt | None:
    return db.scalar(
        select(LessonAttempt).where(
            LessonAttempt.user_id == user_id,
            LessonAttempt.lesson_id == lesson_id,
            LessonAttempt.status == "in_progress",
        )
    )


# --- start / resume ----------------------------------------------------------------------


def start_attempt(
    db: Session, user_id: uuid.UUID, slug: str, *, restart: bool, now: datetime
) -> tuple[AttemptResponse, bool]:
    """Return (response, created). An open attempt is resumed unless ``restart``."""
    lesson = content.get_published_lesson(db, slug)
    existing = _open_attempt(db, user_id, lesson.lesson_id)
    if existing is not None and not restart:
        return _attempt_response(db, user_id, existing, resumed=True), False
    if existing is not None:
        existing.status = "abandoned"

    db.execute(
        pg_insert(UserLessonProgress)
        .values(
            user_id=user_id,
            lesson_id=lesson.lesson_id,
            first_started_at=now,
            last_activity_at=now,
        )
        .on_conflict_do_update(
            index_elements=["user_id", "lesson_id"], set_={"last_activity_at": now}
        )
    )
    question_count = db.scalar(
        select(func.count())
        .select_from(Question)
        .where(Question.lesson_version_id == lesson.version_id, Question.role == "lesson")
    )
    attempt = LessonAttempt(
        user_id=user_id,
        lesson_id=lesson.lesson_id,
        lesson_version_id=lesson.version_id,
        status="in_progress",
        is_first_completion=False,
        question_count=question_count or 0,
        started_at=now,
    )
    try:
        with db.begin_nested():
            db.add(attempt)
    except IntegrityError:
        # a concurrent request opened an attempt first; resume that one
        db.commit()
        winner = _open_attempt(db, user_id, lesson.lesson_id)
        if winner is None:
            raise
        return _attempt_response(db, user_id, winner, resumed=True), False
    db.commit()
    return _attempt_response(db, user_id, attempt, resumed=False), True


def get_attempt(db: Session, user_id: uuid.UUID, attempt_id: uuid.UUID) -> AttemptResponse:
    attempt = get_owned_attempt(db, user_id, attempt_id)
    return _attempt_response(db, user_id, attempt, resumed=attempt.status == "in_progress")


# --- answers ------------------------------------------------------------------------------


def submit_answer(
    db: Session,
    user_id: uuid.UUID,
    attempt_id: uuid.UUID,
    *,
    question_id: uuid.UUID,
    selected: list[uuid.UUID],
    value: float | None = None,
    now: datetime,
) -> tuple[AnswerResponse, bool]:
    """Grade and store the first answer to a question. Return (response, created).

    Replays return the stored result: the first answer is final.
    """
    attempt = get_owned_attempt(db, user_id, attempt_id, lock=True)
    questions = _lesson_questions(db, attempt.lesson_version_id)
    stored = db.scalar(
        select(LessonAttemptAnswer).where(
            LessonAttemptAnswer.attempt_id == attempt.id,
            LessonAttemptAnswer.question_id == question_id,
        )
    )
    if stored is not None and question_id in questions:
        result = _answer_result(attempt, questions[question_id], stored)
        db.commit()
        return AnswerResponse(**result.model_dump(), replayed=True), False
    if attempt.status != "in_progress":
        raise AttemptNotOpenError
    lq = questions.get(question_id)
    if lq is None:
        raise QuestionNotInAttemptError(details=[{"field": "question_id", "issue": "unknown"}])
    config = lq.question.estimate
    problem = estimate_problem(value, config)
    if problem:
        raise SelectionError(code=problem, details=[{"field": "value", "issue": problem.lower()}])
    if config is None or value is None:
        problem = selection_problem(lq.question.type, selected, [o.id for o in lq.options])
        if problem:
            raise SelectionError(
                code=problem, details=[{"field": "selected_option_ids", "issue": problem.lower()}]
            )
        correct = is_correct(selected, [o.id for o in lq.options if o.is_correct])
    else:
        correct = estimate_correct(value, config)

    answer = LessonAttemptAnswer(
        attempt_id=attempt.id,
        question_id=question_id,
        selected_option_ids=selected,
        value=value,
        is_correct=correct,
        answered_at=now,
    )
    db.add(answer)
    progress = _progress(db, user_id, attempt.lesson_id)
    if progress is not None:
        progress.last_activity_at = now
    day = to_local_date(now, get_preferences(db, user_id).timezone)
    gamification.on_lesson_question_answered(db, user_id, day)
    db.commit()
    result = _answer_result(attempt, lq, answer)
    return AnswerResponse(**result.model_dump(), replayed=False), True


# --- completion ---------------------------------------------------------------------------


def complete_attempt(
    db: Session, user_id: uuid.UUID, attempt_id: uuid.UUID, *, now: datetime
) -> CompletionResponse:
    attempt = get_owned_attempt(db, user_id, attempt_id, lock=True)
    if attempt.status == "completed":
        today = to_local_date(now, get_preferences(db, user_id).timezone)
        rewards = gamification.rewards_for_attempt(db, user_id, attempt.id)
        response = _completion_response(
            db, user_id, attempt, rewards=rewards, today=today, replayed=True
        )
        db.commit()
        return response
    if attempt.status != "in_progress":
        raise AttemptNotOpenError

    answers = {
        a.question_id: a
        for a in db.scalars(
            select(LessonAttemptAnswer).where(LessonAttemptAnswer.attempt_id == attempt.id)
        )
    }
    missing = [
        qid for qid in _lesson_questions(db, attempt.lesson_version_id) if qid not in answers
    ]
    if missing:
        raise AttemptIncompleteError(details=[{"question_id": str(qid)} for qid in missing])

    timezone = get_preferences(db, user_id).timezone
    local_today = to_local_date(now, timezone)
    progress = db.scalar(
        select(UserLessonProgress)
        .where(
            UserLessonProgress.user_id == user_id,
            UserLessonProgress.lesson_id == attempt.lesson_id,
        )
        .with_for_update()
    )
    if progress is None:  # created at start; defensive for attempts predating progress rows
        progress = UserLessonProgress(
            user_id=user_id,
            lesson_id=attempt.lesson_id,
            first_started_at=attempt.started_at,
            completion_count=0,
            last_activity_at=now,
        )
        db.add(progress)
    first_completion = progress.first_completed_at is None
    correct = sum(a.is_correct for a in answers.values())

    attempt.status = "completed"
    attempt.completed_at = now
    attempt.local_date_completed = local_today
    attempt.correct_first_try = correct
    attempt.is_first_completion = first_completion

    progress.completion_count += 1
    progress.last_activity_at = now
    if first_completion:
        progress.first_completed_at = now
        progress.first_attempt_score = correct
        initial = scheduler.initial_state(local_today)
        db.execute(
            pg_insert(ReviewState)
            .values(
                user_id=user_id,
                lesson_id=attempt.lesson_id,
                scheduler_version=scheduler.version,
                ease_factor=initial.ease_factor,
                interval_days=initial.interval_days,
                repetitions=initial.repetitions,
                lapses=initial.lapses,
                due_on=initial.due_on,
            )
            .on_conflict_do_nothing(index_elements=["user_id", "lesson_id"])
        )
    db.flush()
    rewards = gamification.on_lesson_completed(
        db,
        user_id,
        attempt_id=attempt.id,
        lesson_id=attempt.lesson_id,
        first_completion=first_completion,
        perfect=first_completion and correct == attempt.question_count,
        day=local_today,
        now=now,
    )
    db.flush()
    response = _completion_response(
        db, user_id, attempt, rewards=rewards, today=local_today, replayed=False
    )
    db.commit()
    return response


def _completion_response(
    db: Session,
    user_id: uuid.UUID,
    attempt: LessonAttempt,
    *,
    rewards: gamification.Rewards,
    today: date,
    replayed: bool,
) -> CompletionResponse:
    """Rebuilt from stored data, so replays return the same summary."""
    first_review_on = None
    if attempt.is_first_completion and attempt.local_date_completed is not None:
        first_review_on = attempt.local_date_completed + timedelta(days=1)
    return CompletionResponse(
        attempt=CompletedAttemptOut(
            id=attempt.id,
            status="completed",
            correct_first_try=attempt.correct_first_try or 0,
            question_count=attempt.question_count,
            is_first_completion=attempt.is_first_completion,
        ),
        first_review_on=first_review_on,
        next_lesson=discover.next_lesson_after(db, user_id, attempt.lesson_id),
        xp_awarded=rewards.xp_awarded,
        xp=gamification.xp_summary(db, user_id, today, reached_now=rewards.daily_goal_reached_now),
        streak=gamification.streak_out(db, user_id, today),
        achievements_unlocked=rewards.achievements_unlocked,
        replayed=replayed,
    )
