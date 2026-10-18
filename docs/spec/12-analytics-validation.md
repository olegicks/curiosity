# 12 — Product Analytics and Validation Hypotheses

The MVP has to answer two different questions. Each metric below is tagged with the one it answers:

- **Usage**: do people come back and finish what they start?
- **Learning**: do people actually understand and remember?

Opening the app or completing a lesson is **usage, not proof of learning**. Learning claims rest only on scored, delayed recall.

**No results are claimed in this document.** The targets below are experimental hypotheses to test with real users. They are not industry benchmarks and have not been achieved.

## 12.1 Data sources

Most metrics come from **domain tables**, which are authoritative and already written transactionally: `users`, `daily_activity`, `lesson_attempts`, `lesson_attempt_answers`, `review_sessions`, `review_events`, `ai_requests`, `ai_explanation_feedback`, `lesson_ratings`. `product_events` covers what domain tables cannot (app opens, screen views, AI sheet opens).

The MVP has no dashboards. The metrics are SQL queries kept in `apps/api/analytics/queries/*.sql` and run with `curiosity analytics report --from --to`, which prints a table.

**Global exclusions** (all metrics): `users.is_internal = true`; deleted accounts (no longer in the data, a known bias); events from non-production environments (separate databases).

**Cohort day** for a user = the local date of their **first learning-active day** (`MIN(daily_activity.local_date)` where answered questions > 0). Users who never answered a question are counted only in the activation metric.

## 12.2 Event catalogue

Server-side domain facts are not duplicated as events. Client events (`POST /events` whitelist):

| Event | Properties | Purpose |
|---|---|---|
| `app_opened` | `cold_start: bool` | Usage without learning |
| `screen_viewed` | `screen: discover\|learn\|recall\|lesson_intro\|profile\|settings` | Navigation sanity checks |
| `onboarding_step` | `step: interests\|goal`, `action: continue\|skip` | Onboarding friction |
| `lesson_step_viewed` | `attempt_id`, `step_index`, `step_type` | Where lessons lose people |
| `ai_sheet_opened` | `lesson_slug`, `step_type` | AI demand vs usage |
| `upgrade_prompt` | `action: shown\|accepted\|dismissed`, `trigger: first_lesson\|third_lesson\|profile` | Conversion |
| `review_session_closed` | `session_id`, `answered`, `total` | Abandonment context |

Server-emitted events (written in the same transaction as the action): `guest_created`, `account_upgraded`, `account_deleted` (written anonymised, `user_id` NULL, before the cascade).

## 12.3 Metric definitions

### M1 — Day-7 retention (Usage) · target ≥ 20%
- **Numerator:** users in the cohort who have a **learning-active day** exactly on cohort day + 7 (local).
- **Denominator:** users whose cohort day falls in the measurement window.
- **Window:** cohorts with cohort day in [T₀, T₁]. Measured once T₁ + 8 days have passed.
- **Exclusions:** global exclusions. Users created less than 8 days before the analysis date.
- **Secondary (reported, not a target):** "Week-2 retention" = learning-active on any day in cohort day + 7 … + 13. "D7 open retention" = `app_opened` on day 7 (gap vs M1 = opened without learning).
- **Minimum sample:** ≥ 100 cohort users before drawing a conclusion. The 95% Wilson interval is reported alongside the value.

### M2 — Review session completion (Usage) · target ≥ 50%
- **Numerator:** review sessions with `status = completed` (all items answered).
- **Denominator:** review sessions **started**, meaning created with ≥ 1 item **and** at least 1 item answered. Sessions created but never touched are excluded, because they mostly reflect opening the tab.
- **Window:** sessions with `local_date` in [T₀, T₁].
- **Exclusions:** global. Sessions still `open` with today's local date at analysis time.
- **Secondary:** completion by session size bucket (1–3, 4–10, 11–20).

### M3 — Accuracy improvement on repeated concept assessment (Learning) · hypothesis: positive improvement
- **Unit:** (user, concept) pairs with ≥ 3 review events.
- **Measure:** accuracy at review #3 minus accuracy at review #1, computed over the same set of pairs (paired comparison, so the population stays fixed).
- **Caveat:** different review numbers use different questions. Because questions are assigned at random, item difficulty averages out. The report also gives item-level accuracy (p-values) per question to detect bad items.
- **Survivorship caveat:** failing review #1 resets the interval, so review #3 may happen sooner for failed concepts. A secondary analysis restricts to pairs whose first review succeeded and reports success at the 15-day interval.
- **Target interpretation:** a positive difference with a 95% CI excluding 0, on ≥ 200 pairs.

### M4 — Recall after increasing intervals (Learning) · hypothesis: ≥ 70% success at intervals ≥ 14 days
- **Numerator:** `review_events` with `interval_before ≥ 14` and `is_correct = true`.
- **Denominator:** `review_events` with `interval_before ≥ 14`.
- Also reported as a curve: success rate by `interval_before` bucket (1, 6, 7–13, 14–30, 31–90, 91+).
- **Exclusions:** `guessed = true` counted separately (reported both ways). Global exclusions.
- **Why 70%:** an assumed threshold (D-12). With 3–5 option questions, chance is 20–33%, so 70% indicates real retention. The value needs product owner approval.

### M5 — AI cost per active learner (Cost) · hypothesis: ≤ USD 0.10 per monthly active learner
- **Numerator:** `SUM(ai_requests.cost_micros)` in a 28-day window.
- **Denominator:** distinct users with ≥ 1 learning-active day in the same window.
- **Also reported:** cache hit rate (`cache_hit / all non-rate-limited requests`), the share of learners who used AI at least once, failures by outcome, and cost per generation.
- **Exclusions:** CLI pre-generation writes no `ai_requests` rows. Its cost is recorded only on `ai_explanations.cost_micros` and reported separately as one-off content cost. Requests from accounts deleted later (`user_id NULL`) still count in the numerator.

### M6 — Explanation clarity (Qualitative + proxy)
- **Proxy A:** lesson clarity rating = `clear / (clear + unclear)` per lesson version (only versions with ≥ 20 ratings are shown).
- **Proxy B:** AI explanation helpfulness = `helpful / all ratings`, per mode. Incorrect-flag rate per 100 served explanations.
- **Qualitative:** 6–10 moderated interviews with target-persona users after ≥ 1 week of use. Script: think-aloud through one new lesson, then a comparison task (the same concept explained by a general-purpose chatbot vs the Curiosity lesson, order randomised) with the questions "Which helped you understand more? Why?" Findings are recorded verbatim in `docs/research/` (no PII).
- **Hypothesis:** most interviewees prefer the Curiosity lesson for clarity and trustworthiness, with specific reasons. Answers are reported as counts plus quotes, not as statistics.

### M7 — Activation (Usage, supporting)
- Share of new guests who complete ≥ 1 lesson within their first session day. Hypothesis: ≥ 60%.

### M8 — Content quality signals (supporting)
- Per question: accuracy, plus the share of incorrect answers picking each distractor. A question with accuracy > 95% or < 25% over ≥ 50 answers is flagged for editorial review.
- Content reports per 1,000 lesson completions.

## 12.4 Validation plan

1. **Closed beta:** TestFlight and Play internal testing, 30–100 target users recruited from student and professional networks. All are marked as regular users (not internal).
2. **Run length:** at least 4 weeks after the last cohort joins, so that 14+ day intervals occur for most active users (M4 needs time).
3. **Decision rules (proposed, D-12):**
   - M1 ≥ 20% **and** M4 ≥ 70% → continue and expand content (more topics in psychology).
   - M1 < 20% but M4 ≥ 70% → the learning works but the habit doesn't. Investigate reminders and session length (the deferred notification feature becomes a candidate).
   - M4 < 70% → revisit the question design and scheduler before growth work.
   - M5 > target → switch the model, increase pre-generation, or lower limits.
4. **Reporting:** a one-page results note with the values, confidence intervals, sample sizes, and known biases. Missing or insufficient data is stated explicitly.
