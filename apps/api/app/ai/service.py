"""Alternative explanations: cache, limits, generation, feedback (docs/spec/08).

AI never blocks learning: this module has its own endpoints and transactions,
and every failure maps to a clean 429/503 for the client to show inline.
"""

import math
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

import structlog
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.ai import guard, pricing
from app.ai.models import AiExplanation, AiExplanationFeedback, AiRequest
from app.ai.prompts import PROMPT_VERSION, SYSTEM_PROMPT, Mode, lesson_context, user_message
from app.ai.provider import (
    ExplanationProvider,
    GenerationRequest,
    GenerationResult,
    ProviderError,
    ProviderTimeoutError,
)
from app.ai.schemas import ExplanationOut, ExplanationResponse, UsageOut
from app.config import Settings
from app.content import service as content
from app.content.models import LessonVersion, LessonVersionSource, Source
from app.core.errors import AppError, NotFoundError, RateLimitedError, ValidationError
from app.learning.models import LessonAttempt

log = structlog.get_logger(__name__)

VISIBLE = ("approved", "generated")
FLAGS_TO_HIDE = 2
DAY = timedelta(hours=24)
BURST_WINDOW = timedelta(seconds=60)


class AiRateLimitedError(RateLimitedError):
    code = "AI_RATE_LIMITED"
    message = "You've reached the limit for alternative explanations."


class AiUnavailableError(AppError):
    status_code = 503
    code = "AI_UNAVAILABLE"
    message = "Alternative explanations aren't available right now."

    def __init__(self, reason: str) -> None:
        super().__init__(details=[{"reason": reason}])


class AiDisabledError(AppError):
    status_code = 503
    code = "AI_DISABLED"
    message = "Alternative explanations are turned off."


class VersionNotAvailableError(ValidationError):
    code = "VERSION_NOT_AVAILABLE"
    message = "This lesson version is not available."


class ExplanationNotFoundError(NotFoundError):
    code = "EXPLANATION_NOT_FOUND"
    message = "Explanation not found."


@dataclass(frozen=True)
class _Context:
    user_id: uuid.UUID
    version_id: uuid.UUID
    mode: Mode
    now: datetime


# --- usage log and limits -------------------------------------------------------------------


def _log(
    db: Session,
    ctx: _Context,
    outcome: str,
    *,
    explanation_id: uuid.UUID | None = None,
    result: GenerationResult | None = None,
    cost: int = 0,
    latency_ms: int = 0,
) -> None:
    db.add(
        AiRequest(
            user_id=ctx.user_id,
            lesson_version_id=ctx.version_id,
            mode=ctx.mode,
            explanation_id=explanation_id,
            outcome=outcome,
            model=result.model if result else None,
            input_tokens=result.input_tokens if result else 0,
            output_tokens=result.output_tokens if result else 0,
            cost_micros=cost,
            latency_ms=latency_ms,
            created_at=ctx.now,
        )
    )
    log.info("ai_request", outcome=outcome, mode=ctx.mode, cost_micros=cost, latency_ms=latency_ms)


def _counted_since(db: Session, user_id: uuid.UUID, since: datetime) -> list[datetime]:
    """Request times that count against the user's limits (rate-limited ones don't)."""
    return list(
        db.scalars(
            select(AiRequest.created_at)
            .where(
                AiRequest.user_id == user_id,
                AiRequest.created_at > since,
                AiRequest.outcome != "rate_limited",
            )
            .order_by(AiRequest.created_at)
        )
    )


def _check_user_limits(db: Session, ctx: _Context, settings: Settings) -> None:
    for window, limit in (
        (BURST_WINDOW, settings.ai_user_burst_limit),
        (DAY, settings.ai_user_daily_limit),
    ):
        times = _counted_since(db, ctx.user_id, ctx.now - window)
        if len(times) >= limit:
            retry_after = math.ceil((times[0] + window - ctx.now).total_seconds())
            _log(db, ctx, "rate_limited")
            db.commit()
            raise AiRateLimitedError(headers={"Retry-After": str(max(retry_after, 1))})


def _spent_today(db: Session, now: datetime) -> int:
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)  # UTC day
    return int(
        db.scalar(
            select(func.coalesce(func.sum(AiRequest.cost_micros), 0)).where(
                AiRequest.created_at >= start
            )
        )
        or 0
    )


def _usage(db: Session, user_id: uuid.UUID, now: datetime, settings: Settings) -> UsageOut:
    used = len(_counted_since(db, user_id, now - DAY))
    return UsageOut(
        remaining_today=max(settings.ai_user_daily_limit - used, 0),
        limit_per_day=settings.ai_user_daily_limit,
    )


# --- cache ------------------------------------------------------------------------------------


def _variants(db: Session, ctx: _Context) -> list[AiExplanation]:
    return list(
        db.scalars(
            select(AiExplanation)
            .where(
                AiExplanation.lesson_version_id == ctx.version_id,
                AiExplanation.mode == ctx.mode,
                AiExplanation.prompt_version == PROMPT_VERSION,
            )
            .order_by(AiExplanation.variant)
        )
    )


def _pick(variants: list[AiExplanation], exclude: set[uuid.UUID]) -> AiExplanation | None:
    visible = [v for v in variants if v.status in VISIBLE and v.id not in exclude]
    approved = [v for v in visible if v.status == "approved"]
    if approved:
        return approved[0]
    return visible[0] if visible else None


def _out(
    chosen: AiExplanation,
    variants: list[AiExplanation],
    exclude: set[uuid.UUID],
    settings: Settings,
) -> ExplanationOut:
    seen = exclude | {chosen.id}
    unseen_cached = any(v.status in VISIBLE and v.id not in seen for v in variants)
    return ExplanationOut(
        id=chosen.id,
        mode=chosen.mode,
        content=chosen.content,
        label="ai_reviewed" if chosen.status == "approved" else "ai_generated",
        variant=chosen.variant,
        has_more_variants=unseen_cached or len(variants) < settings.ai_max_variants,
    )


# --- generation -------------------------------------------------------------------------------


def _resolve_version(
    db: Session, user_id: uuid.UUID, slug: str, version_id: uuid.UUID
) -> LessonVersion:
    lesson = content.get_published_lesson(db, slug)
    if version_id != lesson.version_id:
        pinned = db.scalar(
            select(LessonAttempt.id).where(
                LessonAttempt.user_id == user_id,
                LessonAttempt.lesson_id == lesson.lesson_id,
                LessonAttempt.lesson_version_id == version_id,
                LessonAttempt.status == "in_progress",
            )
        )
        if pinned is None:
            raise VersionNotAvailableError(details=[{"field": "lesson_version_id"}])
    version = db.get(LessonVersion, version_id)
    assert version is not None  # noqa: S101 - FK of the published lesson or attempt
    return version


def lesson_text_for_version(db: Session, version: LessonVersion) -> str:
    citations = list(
        db.scalars(
            select(Source.citation)
            .join(LessonVersionSource, LessonVersionSource.source_id == Source.id)
            .where(LessonVersionSource.lesson_version_id == version.id)
            .order_by(LessonVersionSource.position)
        )
    )
    return lesson_context(
        version.title, version.learning_objective, version.body["steps"], citations
    )


def _generate(
    db: Session,
    ctx: _Context,
    lesson_text: str,
    provider: ExplanationProvider,
    settings: Settings,
) -> tuple[GenerationResult, str] | None:
    """Call the provider (at most two tries on bad output). Returns (result, text) or None."""
    request = GenerationRequest(
        system=SYSTEM_PROMPT,
        user=user_message(lesson_text, ctx.mode),
        max_tokens=settings.ai_max_output_tokens,
    )
    for _ in range(2):
        if _spent_today(db, ctx.now) >= settings.ai_daily_budget_micros:
            _log(db, ctx, "budget_exceeded")
            db.commit()
            raise AiUnavailableError("budget")
        started = time.perf_counter()
        try:
            result = provider.generate(request)
        except ProviderTimeoutError:
            _log(db, ctx, "timeout", latency_ms=_ms(started))
            db.commit()
            raise AiUnavailableError("timeout") from None
        except ProviderError:
            _log(db, ctx, "provider_error", latency_ms=_ms(started))
            db.commit()
            raise AiUnavailableError("provider") from None
        cost = pricing.cost_micros(
            settings, result.model, result.input_tokens, result.output_tokens
        )
        problem = (
            "provider_" + result.status
            if result.status != "ok"
            else guard.output_problem(result.text, lesson_text)
        )
        if problem is None:
            return result, result.text.strip()
        log.warning("ai_output_rejected", reason=problem, mode=ctx.mode)
        _log(db, ctx, "invalid_output", result=result, cost=cost, latency_ms=_ms(started))
        db.flush()
    return None


def _ms(started: float) -> int:
    return round((time.perf_counter() - started) * 1000)


def explain(
    db: Session,
    user_id: uuid.UUID,
    slug: str,
    *,
    mode: Mode,
    version_id: uuid.UUID,
    exclude_ids: list[uuid.UUID],
    now: datetime,
    settings: Settings,
    provider: ExplanationProvider,
) -> ExplanationResponse:
    version = _resolve_version(db, user_id, slug, version_id)
    ctx = _Context(user_id=user_id, version_id=version.id, mode=mode, now=now)
    if not settings.ai_explanations_enabled:
        _log(db, ctx, "disabled")
        db.commit()
        raise AiDisabledError
    _check_user_limits(db, ctx, settings)
    exclude = set(exclude_ids)

    def serve(chosen: AiExplanation, variants: list[AiExplanation]) -> ExplanationResponse:
        _log(db, ctx, "cache_hit", explanation_id=chosen.id)
        db.commit()
        return ExplanationResponse(
            explanation=_out(chosen, variants, exclude, settings),
            usage=_usage(db, user_id, now, settings),
        )

    variants = _variants(db, ctx)
    cached = _pick(variants, exclude)
    if cached is not None:
        return serve(cached, variants)
    if len(variants) >= settings.ai_max_variants:
        # every variant was seen (or hidden): cycle back instead of generating more
        cycled = _pick(variants, set())
        if cycled is None:
            raise AiUnavailableError("quality")
        return serve(cycled, variants)

    # One generator per (version, mode, prompt): others wait, then find it cached.
    key = f"ai:{version.id}:{mode}:{PROMPT_VERSION}"
    db.execute(select(func.pg_advisory_xact_lock(func.hashtext(key))))
    variants = _variants(db, ctx)
    cached = _pick(variants, exclude)
    if cached is not None:
        return serve(cached, variants)

    generated = _generate(db, ctx, lesson_text_for_version(db, version), provider, settings)
    if generated is None:
        db.commit()
        raise AiUnavailableError("quality")
    result, text = generated
    cost = pricing.cost_micros(settings, result.model, result.input_tokens, result.output_tokens)
    explanation = AiExplanation(
        lesson_version_id=version.id,
        mode=mode,
        variant=max((v.variant for v in variants), default=0) + 1,
        prompt_version=PROMPT_VERSION,
        model=result.model,
        content=text,
        status="generated",
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        cost_micros=cost,
    )
    db.add(explanation)
    db.flush()
    _log(db, ctx, "generated", explanation_id=explanation.id, result=result, cost=cost)
    db.commit()
    return ExplanationResponse(
        explanation=_out(explanation, [*variants, explanation], exclude, settings),
        usage=_usage(db, user_id, now, settings),
    )


# --- feedback ---------------------------------------------------------------------------------


def record_feedback(
    db: Session, user_id: uuid.UUID, explanation_id: uuid.UUID, rating: str
) -> None:
    """Upsert the user's rating. Two distinct 'incorrect' flags hide a generated explanation."""
    received = db.scalar(
        select(AiRequest.id).where(
            AiRequest.user_id == user_id, AiRequest.explanation_id == explanation_id
        )
    )
    explanation = db.scalar(
        select(AiExplanation).where(AiExplanation.id == explanation_id).with_for_update()
    )
    if received is None or explanation is None:
        raise ExplanationNotFoundError
    db.execute(
        pg_insert(AiExplanationFeedback)
        .values(explanation_id=explanation_id, user_id=user_id, rating=rating)
        .on_conflict_do_update(
            index_elements=["explanation_id", "user_id"], set_={"rating": rating}
        )
    )
    explanation.flag_count = int(
        db.scalar(
            select(func.count())
            .select_from(AiExplanationFeedback)
            .where(
                AiExplanationFeedback.explanation_id == explanation_id,
                AiExplanationFeedback.rating == "incorrect",
            )
        )
        or 0
    )
    if explanation.status == "generated" and explanation.flag_count >= FLAGS_TO_HIDE:
        explanation.status = "hidden"
        log.info("ai_explanation_hidden", explanation_id=str(explanation_id))
    db.commit()
