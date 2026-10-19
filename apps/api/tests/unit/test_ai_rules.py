"""Guard, pricing, prompt and Anthropic provider adapter (T-AI-5, T-AI-8)."""

from types import SimpleNamespace
from typing import Any

import anthropic
import httpx2
import pytest

from app.ai import guard, pricing
from app.ai.prompts import SYSTEM_PROMPT, lesson_context, user_message
from app.ai.provider import (
    FAKE_TEXT,
    REFUSAL_FALLBACK_BETA,
    AnthropicProvider,
    GenerationRequest,
    ProviderError,
    ProviderTimeoutError,
)
from app.config import AiProvider
from tests.conftest import make_settings

LESSON = (
    "Anchoring: the first number you see pulls later estimates toward it. "
    "In one study people saw 10 or 65 first."
)
GOOD = " ".join(["The first number you hear acts like a starting point for your guess."] * 4)

# --- guard -------------------------------------------------------------------------------------


def test_guard_accepts_a_faithful_explanation() -> None:
    assert guard.output_problem(GOOD, LESSON) is None
    assert guard.output_problem(GOOD + " Seeing 65 first matters.", LESSON) is None


@pytest.mark.parametrize(
    ("text", "problem"),
    [
        ("Too short.", "too_short"),
        (" ".join(["word"] * 251), "too_long"),
        (GOOD + " See https://example.com.", "link"),
        (GOOD + " Mail me at a@b.co.", "link"),
        ("# Heading\n" + GOOD, "markup"),
        (GOOD + " [more](x)", "markup"),
        (GOOD + " <b>bold</b>", "markup"),
        (GOOD + " About 73% of people do this.", "unsupported_number"),
        (GOOD + " This was shown in 1974.", "unsupported_number"),
        (GOOD + " Researchers found it everywhere.", "unsupported_citation"),
        (GOOD + " Smith et al. agree.", "unsupported_citation"),
        (GOOD + " As an AI, I think so.", "blocked_phrase"),
        (GOOD + " This could help diagnose anxiety.", "blocked_phrase"),
    ],
)
def test_guard_rejects(text: str, problem: str) -> None:
    assert guard.output_problem(text, LESSON) == problem


def test_guard_allows_phrases_the_lesson_itself_uses() -> None:
    assert guard.output_problem(GOOD + " In one study people saw it too.", LESSON) is None
    assert guard.output_problem(GOOD + " A study looked at this.", LESSON + " a study") is None


# --- pricing ------------------------------------------------------------------------------------


def test_cost_uses_list_prices_and_rounds_up() -> None:
    settings = make_settings()
    assert pricing.cost_micros(settings, "claude-opus-5-5", 1500, 200) == 6000 + 4000
    assert pricing.cost_micros(settings, "claude-haiku-5-5", 1, 1) == 1  # ceil of 0.6
    assert pricing.cost_micros(settings, "fake", 1500, 200) == 0


def test_unknown_models_are_priced_conservatively_and_overrides_win() -> None:
    settings = make_settings()
    assert pricing.cost_micros(settings, "mystery-model", 1_000_000, 0) == 4_000_000
    custom = make_settings(ai_price_input_per_mtok_micros=1, ai_price_output_per_mtok_micros=2)
    assert pricing.cost_micros(custom, "claude-opus-5-5", 1_000_000, 1_000_000) == 3


# --- prompt -------------------------------------------------------------------------------------


def test_lesson_context_contains_reviewed_content_only() -> None:
    steps: list[dict[str, Any]] = [
        {"type": "hook", "body": "Hook text"},
        {"type": "explanation", "title": "Idea", "body": "Explained."},
        {"type": "question", "question_key": "check-1"},
        {"type": "example", "kind": "illustrative", "body": "Imagine."},
        {"type": "misconception", "myth": "Myth.", "correction": "Fix."},
        {"type": "summary", "points": ["One.", "Two."]},
    ]
    text = lesson_context("Anchoring", "Recognize anchoring.", steps, ["Author (2000)."])
    for expected in ["Lesson: Anchoring", "Explained.", "Illustrative example", "Myth.", "- Two."]:
        assert expected in text
    assert "check-1" not in text
    message = user_message(text, "analogy")
    assert "where the analogy stops working" in message
    assert "hypothetical" in SYSTEM_PROMPT


# --- Anthropic adapter (no network) -------------------------------------------------------------


def _settings(**overrides: Any) -> Any:
    return make_settings(ai_provider=AiProvider.ANTHROPIC, anthropic_api_key="sk-test", **overrides)


def _response(text: str, stop_reason: str = "end_turn") -> SimpleNamespace:
    return SimpleNamespace(
        stop_reason=stop_reason,
        model="claude-opus-5-5",
        content=[SimpleNamespace(type="text", text=text)],
        usage=SimpleNamespace(input_tokens=1200, output_tokens=150),
    )


def _provider(
    monkeypatch: pytest.MonkeyPatch, outcome: Any, **overrides: Any
) -> tuple[AnthropicProvider, list[dict[str, Any]]]:
    provider = AnthropicProvider(_settings(**overrides))
    calls: list[dict[str, Any]] = []

    def create(**kwargs: Any) -> Any:
        calls.append(kwargs)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(provider._client.beta.messages, "create", create)
    return provider, calls


REQUEST = GenerationRequest(system="sys", user="lesson", max_tokens=1024)


def test_anthropic_request_shape_and_parsing(monkeypatch: pytest.MonkeyPatch) -> None:
    provider, calls = _provider(monkeypatch, _response('{"status": "ok", "text": "Hello"}'))
    result = provider.generate(REQUEST)
    assert (result.status, result.text, result.model) == ("ok", "Hello", "claude-opus-5-5")
    assert (result.input_tokens, result.output_tokens) == (1200, 150)
    sent = calls[0]
    assert sent["model"] == "claude-opus-5-5"
    assert sent["output_config"]["effort"] == "low"
    assert sent["output_config"]["format"]["type"] == "json_schema"
    assert sent["betas"] == [REFUSAL_FALLBACK_BETA]
    assert sent["fallbacks"] == "default"
    assert sent["messages"] == [{"role": "user", "content": "lesson"}]


def test_fallback_can_be_turned_off(monkeypatch: pytest.MonkeyPatch) -> None:
    provider, calls = _provider(
        monkeypatch, _response('{"status": "ok", "text": "x"}'), ai_refusal_fallback=False
    )
    provider.generate(REQUEST)
    assert calls[0]["betas"] is anthropic.omit
    assert calls[0]["fallbacks"] is anthropic.omit


@pytest.mark.parametrize(
    "response",
    [
        _response('{"status": "ok", "text": "x"}', stop_reason="refusal"),
        _response('{"status": "ok", "text": "x"}', stop_reason="max_tokens"),
        _response("not json"),
        _response('{"status": "maybe", "text": "x"}'),
    ],
)
def test_unusable_responses_are_invalid(monkeypatch: pytest.MonkeyPatch, response: Any) -> None:
    provider, _ = _provider(monkeypatch, response)
    result = provider.generate(REQUEST)
    assert result.status == "invalid"
    assert result.input_tokens == 1200  # still billed, so still costed


def test_errors_are_mapped(monkeypatch: pytest.MonkeyPatch) -> None:
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    provider, _ = _provider(monkeypatch, anthropic.APITimeoutError(request=request))
    with pytest.raises(ProviderTimeoutError):
        provider.generate(REQUEST)
    provider, _ = _provider(monkeypatch, anthropic.APIConnectionError(request=request))
    with pytest.raises(ProviderError):
        provider.generate(REQUEST)


def test_api_key_is_required_and_never_rendered() -> None:
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        make_settings(ai_provider=AiProvider.ANTHROPIC)
    settings = _settings()
    assert "sk-test" not in repr(settings)
    assert "sk-test" not in settings.model_dump_json()


def test_fake_provider_text_passes_the_guard() -> None:
    assert guard.output_problem(FAKE_TEXT, "") is None
