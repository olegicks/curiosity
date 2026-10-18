# 08 — AI Alternative Explanations

## 8.1 Purpose and principles

The only AI feature in the MVP: a user can ask for an **alternative explanation** of the lesson they are reading, in one of three modes:

| Mode | User-facing label | Intent |
|---|---|---|
| `simpler` | Explain it more simply | Same meaning, plainer words, shorter sentences, no new terms |
| `example` | Give me a practical example | One new everyday scenario that shows the concept, clearly hypothetical |
| `analogy` | Explain it with an analogy | One analogy from an unrelated familiar domain, plus where the analogy breaks down |

Principles:
1. **Supplemental, never canonical.** Generated text is always labeled and visually separated, and it is never stored as lesson content.
2. **Grounded.** The only context is the lesson's own reviewed content, plus the citation titles of its sources.
3. **Optional.** If AI is unavailable, everything else works. The feature can be switched off with `AI_EXPLANATIONS_ENABLED=false`.
4. **Bounded cost.** Shared caching, per-user limits, and a global daily budget circuit breaker.
5. **Backend only.** The client never sees provider keys, prompts, or raw provider errors.

## 8.2 Request workflow

```
POST /lessons/{slug}/explanations {mode, lesson_version_id, exclude_ids}
 1. Auth → resolve lesson + version (current, or pinned by user's open attempt)        → 404/422
 2. Feature flag                                                                       → 503 AI_DISABLED
 3. Per-user limits (count ai_requests rows for user in last 24h / last 60s)            → 429 AI_RATE_LIMITED
 4. Cache lookup: ai_explanations WHERE version, mode, prompt_version, status IN (approved, generated)
                  AND id NOT IN exclude_ids  ORDER BY status='approved' DESC, variant ASC LIMIT 1
      hit  → log ai_requests(outcome=cache_hit) → 200
 5. Variant budget: existing variants for (version, mode, prompt_version) ≥ AI_MAX_VARIANTS (3)
      → no new generation; return the lowest visible variant (all were excluded, so cycle back to the start) → 200, has_more_variants=false
 6. Global budget: SUM(cost_micros) today (UTC) ≥ AI_DAILY_BUDGET_MICROS               → 503 AI_UNAVAILABLE(budget)
 7. Acquire pg_advisory_xact_lock(hash(version, mode, prompt_version)) (prevents stampede);
    re-check cache (another request may have just generated it)
 8. Call provider (timeout AI_TIMEOUT_SECONDS=15, SDK retries 1)
      error/timeout → log ai_requests(outcome=provider_error|timeout, cost if billed) → 503 AI_UNAVAILABLE
 9. Guard output (§8.4)
      fail → log invalid_output (cost recorded) → one regeneration attempt if budget allows, else 503 AI_UNAVAILABLE(quality)
10. Insert ai_explanations(variant = next, status = generated) + ai_requests(outcome=generated, tokens, cost)
11. 200 with label ai_generated (or ai_reviewed if approved)
```

The flow runs synchronously inside the request (no worker). The client shows a skeleton and allows cancellation. If the client cancels, the server still finishes and caches the result.

**Why caching is safe:** the explanation depends only on `(lesson_version, mode, prompt_version)` and contains no user data. One generated variant can therefore be served to every user. With 27 lessons × 3 modes × at most 3 variants, a content version has a hard ceiling of **243 generations**.

**Optional pre-generation and approval (recommended, D-6):** `curiosity ai pregenerate --variants 1` creates variant 1 for every published lesson and mode. `curiosity ai review` walks an editor through them (approve / reject / skip). Approved explanations are labeled `ai_reviewed` ("AI-generated · reviewed by our editors"). Rejected ones are never served. Live generation remains as a fallback for variants 2–3 and for new versions.

## 8.3 Prompt design (`explain-v1`)

Prompts are versioned constants in `app/ai/prompts.py`. Changing the text requires bumping `prompt_version`, which naturally invalidates the cache.

**System prompt (summary of required content):**
- Role: a careful psychology educator rewording an editorially reviewed lesson.
- Rules:
  1. Preserve the lesson's meaning and its learning objective. Do not contradict, extend, or "correct" the lesson.
  2. Use only facts stated in the lesson content provided. Do **not** introduce studies, researchers, statistics, numbers, dates, or quotations that are absent from the lesson.
  3. Present any example as hypothetical ("Imagine…"). Never describe an example as a real study or event.
  4. If the lesson marks something as debated, keep that nuance.
  5. No medical, clinical, legal, or financial advice. No diagnoses.
  6. 80–180 words. Plain text with optional **bold** and short bullet lists, no headings, and no links.
  7. For `analogy`: end with one sentence on where the analogy stops working.
  8. If the request cannot be fulfilled within these rules, return `{"status": "cannot_comply"}`.
- Output format: structured JSON via the API's structured-output feature (`output_config.format` with a JSON schema; the Python SDK's `messages.parse()` validates it): `{"status": "ok" | "cannot_comply", "text": string}`.

**User content:** lesson title, learning objective, explanation steps, example steps (with their kind), misconceptions, evidence steps, summary points, source citation titles, and the requested mode. Question texts and answers are **not** included, so that recall items aren't leaked.

The stable system prompt goes first and the lesson payload after it. The payload is small (~1.5–3k tokens), so prompt caching is not expected to matter. Its effect is checked via `usage.cache_read_input_tokens` rather than assumed.

## 8.4 Output guard (`app/ai/guard.py`, pure, unit-tested)

The output is rejected (`invalid_output`) if:
- it does not parse against the schema, or `status = cannot_comply`, or the stop reason is not normal completion (e.g. `refusal`, `max_tokens`);
- the word count is outside 40–250;
- it contains a URL, email address, or Markdown heading/link/image/HTML;
- it contains a **number** (digits, percentages, or a year-like 4-digit token) not present in the lesson payload;
- it contains a capitalised two-word name followed by a year, or "et al.", "study", "researchers found", or "according to" when the lesson has no such phrase (a heuristic for invented citations);
- it contains blocked phrases (a small list: "as an AI", "I cannot", diagnosis or advice phrases).

The guard is a heuristic net, not proof of accuracy. Labeling and user flagging (§8.6) are the second line of defence.

## 8.5 Limits, budget and cost tracking

| Limit | Default | Enforcement |
|---|---|---|
| Per-user daily requests (cache hits included) | 20 / rolling 24 h | `COUNT(ai_requests)` with `(user_id, created_at)` index |
| Per-user burst | 5 / 60 s | same table |
| Guests | same as full users (D-6) | |
| Variants per (version, mode, prompt) | 3 | unique constraint plus a check |
| Global daily spend | `AI_DAILY_BUDGET_MICROS` = 5,000,000 (USD 5) | `SUM(cost_micros)` today (UTC) |
| Provider timeout | 15 s | SDK client timeout |
| Max output tokens | 1,024 | request parameter |

**Cost computation:** `cost_micros = input_tokens × in_price + output_tokens × out_price`, using the token counts in the provider response's `usage`, including any thinking tokens billed as output. Prices come from `app/ai/pricing.py`, overridable via the `AI_PRICE_INPUT_PER_MTOK_MICROS` and `AI_PRICE_OUTPUT_PER_MTOK_MICROS` environment variables. These are list prices, and the provider invoice remains authoritative.

**Model choice (D-6):** configurable via `AI_MODEL`. The default is `claude-opus-5-5`, the current default model (list price USD 4 / 20 per million input/output tokens as of 2026-10). Use it with low `output_config.effort`, since thinking cannot be disabled on that model. Expected cost per generation is roughly 2.5k input + ≤ 1k output tokens ≈ USD 0.01–0.03. Because of the shared cache, total generation cost per content version is bounded at about 243 × USD 0.03 ≈ USD 7. A cheaper model (e.g. `claude-haiku-5-5`, USD 0.10 / 0.50) is a cost/quality trade-off for the product owner to decide, ideally after comparing outputs on a sample of lessons.

**Refusal handling:** check `stop_reason` before reading content. For Opus-tier models, enable the provider's server-side refusal fallback (`fallbacks: "default"` with the corresponding beta header) so that rare false-positive refusals still yield an answer. A refusal that persists is treated as `invalid_output`.

## 8.6 Feedback and moderation

- Users can rate an explanation: helpful / not helpful / incorrect.
- When **`flag_count ≥ 2`** ("incorrect" flags from distinct users) and the status is `generated`, the status changes to `hidden` in the same transaction, and the explanation stops being served. Approved explanations are not auto-hidden. Instead they appear first in `curiosity ai review --flagged`.
- `curiosity ai review` lists hidden or flagged explanations with their lesson context for an editor to approve or reject.

## 8.7 Failure behaviour (client)

| Server response | Client behaviour |
|---|---|
| 200 | Show panel with AI badge and label |
| 429 `AI_RATE_LIMITED` | "You've reached today's limit for alternative explanations." Buttons disabled until `Retry-After` |
| 503 `AI_UNAVAILABLE` / `AI_DISABLED` | "Alternative explanations aren't available right now. The lesson is unaffected." with Retry (not shown for DISABLED) |
| Network error / timeout (client 20 s) | Same as 503, with Retry |

The lesson player state is never affected by AI calls. They use a separate query, and their errors are caught locally.

## 8.8 Privacy

- No user identifiers or user-written text are sent to the provider. Prompts contain only lesson content.
- The provider API key is held only in backend environment secrets. It is never logged and never sent to the client.
- `ai_requests` rows contain no content and are kept after account deletion with `user_id = NULL` for cost accounting.
