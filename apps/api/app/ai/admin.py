"""Editorial operations on AI explanations, used by the CLI (docs/spec/08 §8.2, §8.6).

Pre-generation writes cost to ai_explanations only, never to ai_requests, so
it stays out of per-user limits and the user-facing cost metric (spec 12 M5).
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import get_args

import structlog
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.ai import guard, pricing
from app.ai.models import AiExplanation
from app.ai.prompts import PROMPT_VERSION, SYSTEM_PROMPT, Mode, user_message
from app.ai.provider import ExplanationProvider, GenerationRequest, ProviderError
from app.ai.service import lesson_text_for_version
from app.config import Settings
from app.content.models import Lesson, LessonVersion

log = structlog.get_logger(__name__)

ALL_MODES: tuple[Mode, ...] = get_args(Mode)
REVIEW_STATUSES = ("approved", "rejected", "hidden", "generated")


@dataclass
class PregenerateSummary:
    created: list[str] = field(default_factory=list)
    skipped: int = 0
    failed: list[str] = field(default_factory=list)
    cost_micros: int = 0
    stopped_by_budget: bool = False


@dataclass(frozen=True)
class ExplanationRow:
    id: uuid.UUID
    lesson_slug: str
    mode: str
    variant: int
    status: str
    flag_count: int
    content: str


def pregenerate(
    db: Session,
    *,
    settings: Settings,
    provider: ExplanationProvider,
    modes: tuple[Mode, ...] = ALL_MODES,
    max_cost_micros: int,
) -> PregenerateSummary:
    """Create variant 1 for every published lesson and mode that has none yet."""
    summary = PregenerateSummary()
    versions = db.execute(
        select(Lesson.slug, LessonVersion)
        .join(LessonVersion, LessonVersion.id == Lesson.current_version_id)
        .where(Lesson.status == "published")
        .order_by(Lesson.slug)
    ).all()
    for slug, version in versions:
        lesson_text = lesson_text_for_version(db, version)
        for mode in modes:
            label = f"{slug}/{mode}"
            exists = db.scalar(
                select(AiExplanation.id).where(
                    AiExplanation.lesson_version_id == version.id,
                    AiExplanation.mode == mode,
                    AiExplanation.prompt_version == PROMPT_VERSION,
                )
            )
            if exists is not None:
                summary.skipped += 1
                continue
            if summary.cost_micros >= max_cost_micros:
                summary.stopped_by_budget = True
                return summary
            request = GenerationRequest(
                system=SYSTEM_PROMPT,
                user=user_message(lesson_text, mode),
                max_tokens=settings.ai_max_output_tokens,
            )
            for _ in range(2):  # one retry on rejected output, as in the request path
                try:
                    result = provider.generate(request)
                except ProviderError:
                    summary.failed.append(label)
                    break
                cost = pricing.cost_micros(
                    settings, result.model, result.input_tokens, result.output_tokens
                )
                summary.cost_micros += cost
                text = result.text.strip()
                if result.status == "ok" and guard.output_problem(text, lesson_text) is None:
                    db.add(
                        AiExplanation(
                            lesson_version_id=version.id,
                            mode=mode,
                            variant=1,
                            prompt_version=PROMPT_VERSION,
                            model=result.model,
                            content=text,
                            status="generated",
                            input_tokens=result.input_tokens,
                            output_tokens=result.output_tokens,
                            cost_micros=cost,
                        )
                    )
                    db.commit()
                    summary.created.append(label)
                    break
            else:
                summary.failed.append(label)
    return summary


def list_explanations(
    db: Session, *, status: str | None = None, flagged: bool = False
) -> list[ExplanationRow]:
    stmt = (
        select(AiExplanation, Lesson.slug)
        .join(LessonVersion, LessonVersion.id == AiExplanation.lesson_version_id)
        .join(Lesson, Lesson.id == LessonVersion.lesson_id)
        .order_by(AiExplanation.flag_count.desc(), Lesson.slug, AiExplanation.mode)
    )
    if status is not None:
        stmt = stmt.where(AiExplanation.status == status)
    if flagged:
        stmt = stmt.where(or_(AiExplanation.flag_count > 0, AiExplanation.status == "hidden"))
    return [
        ExplanationRow(e.id, slug, e.mode, e.variant, e.status, e.flag_count, e.content)
        for e, slug in db.execute(stmt)
    ]


def set_status(db: Session, explanation_id: uuid.UUID, status: str, now: datetime) -> None:
    if status not in REVIEW_STATUSES:
        raise ValueError(f"status must be one of {', '.join(REVIEW_STATUSES)}")
    explanation = db.get(AiExplanation, explanation_id)
    if explanation is None:
        raise LookupError(f"explanation {explanation_id} not found")
    explanation.status = status
    explanation.reviewed_at = now
    db.commit()
    log.info("ai_explanation_reviewed", explanation_id=str(explanation_id), status=status)
