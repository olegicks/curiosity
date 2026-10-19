"""List prices in micro-USD per million tokens (docs/spec/08 §8.5).

The provider invoice is authoritative; these drive the budget circuit breaker
and cost metrics. Override with AI_PRICE_*_PER_MTOK_MICROS.
"""

import math

from app.config import Settings

# (input, output) micro-USD per 1M tokens, Anthropic list prices as of 2026-10.
PRICES: dict[str, tuple[int, int]] = {
    "claude-opus-5-5": (4_000_000, 20_000_000),
    "claude-sonnet-5-5": (2_000_000, 10_000_000),
    "claude-haiku-5-5": (100_000, 500_000),
    "fake": (0, 0),
}
# Unknown models are priced like the most expensive known one so budgets stay safe.
_FALLBACK = max(PRICES.values())


def cost_micros(settings: Settings, model: str, input_tokens: int, output_tokens: int) -> int:
    default_in, default_out = PRICES.get(model, _FALLBACK)
    price_in = settings.ai_price_input_per_mtok_micros
    price_out = settings.ai_price_output_per_mtok_micros
    price_in = default_in if price_in is None else price_in
    price_out = default_out if price_out is None else price_out
    return math.ceil((input_tokens * price_in + output_tokens * price_out) / 1_000_000)
