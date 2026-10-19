"""Explanation providers: the Anthropic API, and a fake for development and tests.

Prompts contain lesson content only, never user data. Keys live in backend
settings and are never logged.
"""

import json
from collections import deque
from dataclasses import dataclass, field
from typing import Literal, Protocol

import anthropic
from anthropic import Omit, omit
from anthropic.types.beta import BetaMessageParam, BetaOutputConfigParam

from app.ai.prompts import OUTPUT_SCHEMA
from app.config import AiProvider, Settings

REFUSAL_FALLBACK_BETA = "server-side-fallback-2026-07-01"


@dataclass(frozen=True)
class GenerationRequest:
    system: str
    user: str
    max_tokens: int


@dataclass(frozen=True)
class GenerationResult:
    status: Literal["ok", "cannot_comply", "invalid"]
    text: str
    model: str
    input_tokens: int
    output_tokens: int


class ProviderError(Exception):
    """The provider failed; the request may or may not have been billed."""


class ProviderTimeoutError(ProviderError):
    pass


class ExplanationProvider(Protocol):
    def generate(self, request: GenerationRequest) -> GenerationResult: ...


class AnthropicProvider:
    def __init__(self, settings: Settings) -> None:
        assert settings.anthropic_api_key is not None  # noqa: S101 - enforced by Settings
        self._client = anthropic.Anthropic(
            api_key=settings.anthropic_api_key.get_secret_value(),
            timeout=settings.ai_timeout_seconds,
            max_retries=1,
        )
        self._model = settings.ai_model
        self._effort = settings.ai_effort
        self._fallback = settings.ai_refusal_fallback

    def generate(self, request: GenerationRequest) -> GenerationResult:
        messages: list[BetaMessageParam] = [{"role": "user", "content": request.user}]
        output_config: BetaOutputConfigParam = {
            "effort": self._effort,
            "format": {"type": "json_schema", "schema": OUTPUT_SCHEMA},
        }
        betas: list[str] | Omit = [REFUSAL_FALLBACK_BETA] if self._fallback else omit
        fallbacks: Literal["default"] | Omit = "default" if self._fallback else omit
        try:
            response = self._client.beta.messages.create(
                model=self._model,
                max_tokens=request.max_tokens,
                system=request.system,
                messages=messages,
                output_config=output_config,
                betas=betas,
                fallbacks=fallbacks,
            )
        except anthropic.APITimeoutError as exc:
            raise ProviderTimeoutError("provider timeout") from exc
        except (anthropic.APIStatusError, anthropic.APIConnectionError) as exc:
            raise ProviderError(type(exc).__name__) from exc

        usage = response.usage
        tokens = (usage.input_tokens or 0, usage.output_tokens or 0)
        if response.stop_reason != "end_turn":  # refusal, max_tokens, ...
            return GenerationResult("invalid", "", response.model, *tokens)
        text = next((b.text for b in response.content if b.type == "text"), "")
        try:
            data = json.loads(text)
            status, body = data["status"], data["text"]
        except (ValueError, KeyError, TypeError):
            return GenerationResult("invalid", "", response.model, *tokens)
        if status not in ("ok", "cannot_comply") or not isinstance(body, str):
            return GenerationResult("invalid", "", response.model, *tokens)
        return GenerationResult(status, body, response.model, *tokens)


FAKE_TEXT = (
    "Imagine you are deciding something quickly. Your mind grabs the first easy cue and "
    "builds a story around it, and that story then shapes what you notice next. That is "
    "the heart of this lesson: a mental shortcut that usually helps, but can quietly "
    "steer you wrong when the easy cue is not the right one. Pausing to ask what else "
    "could be true is a simple way to check yourself."
)


@dataclass
class FakeProvider:
    """Deterministic provider. Queue results or exceptions to script a test."""

    script: deque[GenerationResult | Exception] = field(default_factory=deque)
    calls: list[GenerationRequest] = field(default_factory=list)
    input_tokens: int = 1500
    output_tokens: int = 200

    def generate(self, request: GenerationRequest) -> GenerationResult:
        self.calls.append(request)
        if self.script:
            item = self.script.popleft()
            if isinstance(item, Exception):
                raise item
            return item
        return GenerationResult("ok", FAKE_TEXT, "fake", self.input_tokens, self.output_tokens)


def build_provider(settings: Settings) -> ExplanationProvider:
    if settings.ai_provider == AiProvider.ANTHROPIC:
        return AnthropicProvider(settings)
    return FakeProvider()
