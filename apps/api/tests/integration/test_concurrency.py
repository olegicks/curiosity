"""Concurrent requests with separate, committed sessions (T-LRN-1, T-LRN-6).

These tests commit for real, so they truncate the tables they touched afterwards.
"""

import threading
import uuid
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import Engine, func, select, text
from sqlalchemy.orm import Session, sessionmaker

from app.auth.service import create_guest
from app.content.importer import import_content
from app.content.loader import load_content
from app.content.models import AnswerOption
from app.learning import service
from app.learning.models import LessonAttempt, UserLessonProgress
from app.reviews import service as reviews
from app.reviews.models import ReviewEvent, ReviewSession, ReviewState
from tests.conftest import TEST_NOW, make_settings
from tests.content_factory import standard_lessons, write_content

pytestmark = pytest.mark.db


@pytest.fixture
def committed(db_engine: Engine, tmp_path: Path) -> Iterator[sessionmaker[Session]]:
    factory = sessionmaker(db_engine, expire_on_commit=False)
    with factory() as db:
        content = load_content(write_content(tmp_path, standard_lessons()), today=TEST_NOW.date())
        import_content(db, content, now=TEST_NOW)
    yield factory
    with db_engine.begin() as connection:
        connection.execute(text("TRUNCATE users, subjects, sources CASCADE"))


def run_twice[T](factory: sessionmaker[Session], fn: Callable[[Session], T]) -> list[T]:
    barrier = threading.Barrier(2)

    def worker(_: int) -> T:
        with factory() as db:
            barrier.wait()
            return fn(db)

    with ThreadPoolExecutor(max_workers=2) as pool:
        return list(pool.map(worker, range(2)))


def test_concurrent_starts_open_one_attempt(committed: sessionmaker[Session]) -> None:
    with committed() as db:
        user, _ = create_guest(db, timezone=None, now=TEST_NOW, settings=make_settings())

    results = run_twice(
        committed,
        lambda db: service.start_attempt(db, user.id, "anchoring", restart=False, now=TEST_NOW),
    )
    assert results[0][0].attempt.id == results[1][0].attempt.id
    assert sorted(created for _, created in results) == [False, True]
    with committed() as db:
        assert db.scalar(select(func.count()).select_from(LessonAttempt)) == 1


def test_concurrent_completion_counts_once(committed: sessionmaker[Session]) -> None:
    with committed() as db:
        user, _ = create_guest(db, timezone=None, now=TEST_NOW, settings=make_settings())
        started, _ = service.start_attempt(db, user.id, "anchoring", restart=False, now=TEST_NOW)
        attempt_id = started.attempt.id
        for question in started.content.questions:
            option = question.options[0].id
            service.submit_answer(
                db, user.id, attempt_id, question_id=question.id, selected=[option], now=TEST_NOW
            )

    results = run_twice(
        committed, lambda db: service.complete_attempt(db, user.id, attempt_id, now=TEST_NOW)
    )
    assert sorted(r.replayed for r in results) == [False, True]
    assert results[0].first_review_on == results[1].first_review_on
    with committed() as db:
        assert db.scalar(select(func.count()).select_from(ReviewState)) == 1
        progress = db.scalars(select(UserLessonProgress)).one()
        assert progress.completion_count == 1


def _guest_with_due_review(factory: sessionmaker[Session]) -> uuid.UUID:
    """A guest who completed 'anchoring' at TEST_NOW (first review due a day later)."""
    with factory() as db:
        user, _ = create_guest(db, timezone=None, now=TEST_NOW, settings=make_settings())
        started, _ = service.start_attempt(db, user.id, "anchoring", restart=False, now=TEST_NOW)
        for question in started.content.questions:
            service.submit_answer(
                db,
                user.id,
                started.attempt.id,
                question_id=question.id,
                selected=[question.options[0].id],
                now=TEST_NOW,
            )
        service.complete_attempt(db, user.id, started.attempt.id, now=TEST_NOW)
        return user.id


def test_concurrent_session_creation_opens_one_session(committed: sessionmaker[Session]) -> None:
    user_id = _guest_with_due_review(committed)
    later = TEST_NOW + timedelta(days=1)
    results = run_twice(committed, lambda db: reviews.start_session(db, user_id, later))
    assert results[0][0].session.id == results[1][0].session.id
    assert sorted(created for _, created in results) == [False, True]
    with committed() as db:
        assert db.scalar(select(func.count()).select_from(ReviewSession)) == 1


def test_concurrent_answers_change_the_schedule_once(committed: sessionmaker[Session]) -> None:
    user_id = _guest_with_due_review(committed)
    later = TEST_NOW + timedelta(days=1)
    with committed() as db:
        session, _ = reviews.start_session(db, user_id, later)
        item = session.session.items[0]
        correct = list(
            db.scalars(
                select(AnswerOption.id).where(
                    AnswerOption.question_id == item.question.id, AnswerOption.is_correct
                )
            )
        )

    results = run_twice(
        committed,
        lambda db: reviews.answer_item(
            db, user_id, session.session.id, item.id, selected=correct, guessed=False, now=later
        ),
    )
    assert sorted(created for _, created in results) == [False, True]
    with committed() as db:
        assert db.scalar(select(func.count()).select_from(ReviewEvent)) == 1
        state = db.scalars(select(ReviewState)).one()
        assert (state.repetitions, state.interval_days) == (1, 6)
