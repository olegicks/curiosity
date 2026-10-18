# 05 — REST API Specification

Base URL: `https://api.<domain>/v1`. JSON over HTTPS only. FastAPI generates the OpenAPI document at `/v1/openapi.json`, which is disabled in production unless `EXPOSE_OPENAPI=true`. The mobile client's TypeScript types are generated from it (see [06](06-architecture.md)).

## 5.1 Conventions

**Authentication**: `Authorization: Bearer <access_token>`. Unless marked **Public**, every endpoint requires a valid access token for a guest or full user. Endpoints marked **Full** reject guests with `403 FULL_ACCOUNT_REQUIRED`.

**Client headers** (all requests): `X-App-Version: 1.0.0`, `X-Platform: ios|android`, `X-Request-ID` (optional, client-generated UUID; echoed back and logged).
If the app version is below `MIN_APP_VERSION`, the API responds `426 UPGRADE_REQUIRED`.

**Authorization rule (global):** every resource with a user owner is loaded with `WHERE id = :id AND user_id = :current_user_id`. A resource that belongs to another user gives **`404`, never `403`**, so that IDs can't be probed. Repository functions take `user_id` as a required argument. Routers never query by ID alone.

**Validation**: Pydantic v2 models with `extra="forbid"`, string length limits, and enum checks. Unknown fields give `422`.

**Error format** (every non-2xx response):

```json
{
  "error": {
    "code": "LESSON_NOT_FOUND",
    "message": "Lesson not found.",
    "details": [{"field": "slug", "issue": "unknown"}],
    "request_id": "0192a7c4-…"
  }
}
```

`message` is safe, generic English for logs and fallbacks. The client shows localised copy keyed by `code`. Internal exceptions become `500 INTERNAL_ERROR` with no details.

**Common errors** (apply to all endpoints and are not repeated below):

| Status | Code | When |
|---|---|---|
| 400 | `BAD_REQUEST` | Malformed JSON |
| 401 | `UNAUTHENTICATED` | Missing, invalid or expired token, or `token_version` mismatch |
| 403 | `FULL_ACCOUNT_REQUIRED` | Guest calling a **Full** endpoint |
| 404 | `NOT_FOUND` / specific | Unknown or foreign resource |
| 422 | `VALIDATION_ERROR` | Schema or field validation failed (`details[]` lists the fields) |
| 426 | `UPGRADE_REQUIRED` | App version too old |
| 429 | `RATE_LIMITED` | Rate limit hit. Includes a `Retry-After` header. |
| 500 | `INTERNAL_ERROR` | Unexpected |
| 503 | `SERVICE_UNAVAILABLE` | DB unavailable or maintenance |

**Idempotency**: state-changing endpoints are **naturally idempotent** through resource state and DB uniqueness (see each endpoint), so no `Idempotency-Key` header is needed. A replayed request returns the **original result** with the status of the original success (`200` for replays of `201`-creating calls is acceptable and documented per endpoint). The response body includes `"replayed": true` where relevant.

**Pagination**: cursor-based where it applies. `?limit=` (1–100, default 20) and `?cursor=<opaque>`. Response: `{"items": [...], "next_cursor": "…" | null}`. Collections that are inherently small (subjects, achievements) are not paginated.

**Timestamps**: UTC ISO-8601. **Local dates**: `YYYY-MM-DD` in the user's timezone.

**Shared schemas** (used below):

```ts
Tokens        = { access_token: string, access_expires_in: number /*s*/, refresh_token: string, token_type: "Bearer" }
UserOut       = { id, is_guest, email: string|null, display_name: string|null, created_at }
Preferences   = { timezone: string, daily_xp_goal: 20|40|60, interest_topics: string[] /*slugs*/, onboarding_completed: boolean }
ProgressBrief = { status: "not_started"|"started"|"completed"|"recalled"|"understood"|"retained",
                  mastery_stage: 0|1|2|3|4, completed_at: string|null, next_review_on: string|null, in_progress_attempt_id: string|null }
LessonSummary = { slug, title, description, topic: {slug, title}, estimated_minutes, evidence_status, position, progress: ProgressBrief }
OptionOut     = { id, text }                        // never includes correctness or feedback before answering
QuestionOut   = { id, type: "single_choice"|"multi_select"|"true_false", prompt, options: OptionOut[] }
Step          = { type: "hook"|"explanation"|"example"|"misconception"|"evidence"|"question"|"summary", ...typed fields; question steps carry question_id }
LessonContent = { lesson_version_id, version, slug, title, learning_objective, estimated_minutes, evidence_status,
                  steps: Step[], questions: QuestionOut[], sources: {key, citation, url, doi}[], related: LessonSummary[] }
AnswerResult  = { question_id, is_correct, selected_option_ids, correct_option_ids, option_feedback: {option_id, feedback, is_correct}[], explanation }
XpAward       = { reason, amount }
Achievement   = { code, title, description, earned_at: string|null }
StreakOut     = { current: number, longest: number, freezes_available: number, done_today: boolean, at_risk: boolean }
```

Options in `QuestionOut` are **shuffled server-side** when `shuffle = true`, using a seed of `(attempt_id or session_item_id, question_id)`, so the order is stable on resume.

---

## 5.2 Auth

### `POST /auth/guest` — **Public**
Creates a guest user with preferences and streak rows.
- Request: `{ "timezone": "Europe/Kyiv" }` (optional; invalid or missing → `UTC`).
- 201: `{ "user": UserOut, "tokens": Tokens }`
- Rate limit: 10/hour per IP (`429`).
- Idempotency: not idempotent (each call creates a guest). The client calls it only from the Welcome screen and stores the result before navigating.

### `POST /auth/register` — **Public**
New full account (for users who don't want a guest first).
- Request: `{ "email": string ≤ 254, "password": string 10–128, "display_name"?: string 1–40, "timezone"?: string }`
- 201: `{ "user": UserOut, "tokens": Tokens }`
- Errors: `409 EMAIL_TAKEN`, `422 WEAK_PASSWORD` (length or common-password list).
- Rate limit: 5/hour per IP.

### `POST /auth/upgrade` — guest token required
Converts the **current guest** into a full account. The same `user.id` keeps all progress.
- Request: `{ "email", "password", "display_name"? }`
- 200: `{ "user": UserOut, "tokens": Tokens }`. All previous refresh tokens are revoked and `token_version` is incremented.
- Errors: `409 EMAIL_TAKEN`, `409 ALREADY_FULL_ACCOUNT`, `422 WEAK_PASSWORD`.
- Idempotency: a repeat call after success returns `409 ALREADY_FULL_ACCOUNT`. The client treats this as success if `GET /me` shows the expected email.

### `POST /auth/login` — **Public**
- Request: `{ "email", "password" }`
- 200: `{ "user": UserOut, "tokens": Tokens }`
- Errors: `401 INVALID_CREDENTIALS` (same response for an unknown email or a wrong password, with constant-time verification against a dummy hash).
- Rate limit: 5/min and 20/hour per (IP, email). 50/hour per IP.

### `POST /auth/refresh` — **Public**
- Request: `{ "refresh_token" }`
- 200: `{ "tokens": Tokens }`. The old token is marked `rotated_at` and a new token is issued in the same family.
- Errors: `401 INVALID_REFRESH_TOKEN` (unknown, expired, or revoked). **Reuse** of an already-rotated token revokes the whole family and returns `401 REFRESH_TOKEN_REUSED`.
- Concurrency: a reuse inside a 10-second grace window from the same family returns the already-issued successor instead of revoking. This handles parallel refreshes from the app.

### `POST /auth/logout`
- Request: `{ "refresh_token" }`
- 204. Revokes that token's family. Idempotent: unknown or already-revoked tokens also return 204.

### `POST /auth/password-reset/request` — **Public**
- Request: `{ "email" }`
- **Always 202** `{}`, whether or not the account exists. If it does, an email with a single-use link `curiosity://reset?token=…` is sent (plus an https fallback page). The token is valid for 30 minutes.
- Rate limit: 3/hour per email, 10/hour per IP.

### `POST /auth/password-reset/confirm` — **Public**
- Request: `{ "token", "new_password" }`
- 204. Sets the password, marks the token used, revokes all refresh tokens, and increments `token_version`.
- Errors: `400 INVALID_RESET_TOKEN` (unknown, expired, or used), `422 WEAK_PASSWORD`.

### `POST /me/password` — **Full**
- Request: `{ "current_password", "new_password" }`
- 200: `{ "tokens": Tokens }`. Other sessions are revoked and the current device gets fresh tokens.
- Errors: `401 INVALID_CREDENTIALS`, `422 WEAK_PASSWORD`. Rate limit 5/hour per user.

---

## 5.3 Current user, preferences, privacy

### `GET /me`
200: `{ "user": UserOut, "preferences": Preferences }`

### `PATCH /me`
Request: `{ "display_name": string 1–40 | null }` → 200 `{ "user": UserOut }`. Display names are trimmed. Control characters are rejected.

### `GET /me/preferences` / `PATCH /me/preferences`
PATCH request (all fields optional): `{ "timezone"?: IANA, "daily_xp_goal"?: 20|40|60, "interest_topics"?: slug[] (≤3, must exist), "onboarding_completed"?: true }`
200: `Preferences`. Errors: `422 INVALID_TIMEZONE`, `422 UNKNOWN_TOPIC`. Idempotent (PATCH semantics).

### `GET /me/export`
Returns a JSON document with all personal data: user, preferences, interests, attempts and answers, progress, review states and events, sessions, XP transactions, streak, daily activity, achievements, AI explanation feedback, lesson ratings, content feedback the user submitted, and product events.
- 200 `application/json` with `Content-Disposition: attachment; filename="curiosity-export-<date>.json"`.
- Rate limit: 3/day per user.

### `DELETE /me`
- Request: full accounts `{ "password": string }`; guests `{ "confirm": "DELETE" }`.
- 204. Hard-deletes the user and every personal row (see [09 §9.6](09-security-privacy.md#96-account-deletion)), in a single transaction.
- Errors: `401 INVALID_CREDENTIALS`, `422 CONFIRMATION_REQUIRED`.
- Idempotency: after deletion, any token is invalid, so a repeat gives `401`. The client treats `401` after a delete request as success.

---

## 5.4 Content discovery

### `GET /subjects`
200: `{ "items": [{ "slug", "title", "topics": [{ "slug", "title", "description", "position", "lesson_count" }] }] }`. Published subjects only.

### `GET /lessons`
Query: `topic?` (slug), `progress?` (`not_started|in_progress|completed`), `limit` (1–100, default 20), `cursor?`.
Ordered by topic position, then lesson position.
200: `{ "items": LessonSummary[], "next_cursor": string|null }`. Published lessons only.

### `GET /lessons/{slug}`
200:
```json
{
  "lesson": { "...LessonSummary": "...", "learning_objective": "…", "related": [/* LessonSummary */] },
  "content": { /* LessonContent of the current published version, without answers */ }
}
```
Errors: `404 LESSON_NOT_FOUND` (unknown, draft, or retired).

### `GET /discover`
200:
```json
{
  "local_date": "2026-11-03",
  "primary_action": {
    "type": "review",                       // review | continue_lesson | start_lesson | caught_up
    "review": { "due_count": 5, "estimated_minutes": 3, "open_session_id": null },
    "lesson": null,                         // LessonSummary for continue/start
    "attempt_id": null,
    "next_review_on": null                  // for caught_up
  },
  "todays_lesson": { "slug": "anchoring", "title": "Anchoring", "...": "LessonSummary" },
  "recommended": [ /* up to 4 LessonSummary */ ],
  "progress": { "lessons_total": 27, "completed": 4, "understood": 1 },
  "streak": { "current": 3, "longest": 5, "freezes_available": 1, "done_today": false, "at_risk": false },
  "xp": { "today": 15, "goal": 20, "total": 140 },
  "reviews_due": 5
}
```
Estimated review minutes = `ceil(due_count × 0.5)`.

---

## 5.5 Lessons: attempts and answers

### `POST /lessons/{slug}/attempts`
Start or resume.
- Request: `{ "restart"?: boolean }` (default false).
- Behaviour:
  - If there is an open attempt and `restart` is false → **200** with the existing attempt (`"resumed": true`).
  - If there is an open attempt and `restart` is true → the old attempt is marked `abandoned` and a new one is created → 201.
  - If there is no open attempt → 201.
- 201/200:
```json
{
  "attempt": {
    "id": "0192…", "status": "in_progress", "lesson_version_id": "…", "started_at": "…",
    "answers": [ /* AnswerResult[] already given in this attempt (for resume) */ ],
    "is_revisit": false
  },
  "content": { /* LessonContent for the pinned version */ },
  "resumed": false
}
```
- Errors: `404 LESSON_NOT_FOUND`.
- Concurrency: two simultaneous starts → the partial unique index lets one insert succeed, and the other request re-reads and returns that attempt (200).

### `GET /attempts/{attempt_id}`
200: same shape as above. `404 ATTEMPT_NOT_FOUND` for a foreign or unknown attempt.

### `POST /attempts/{attempt_id}/answers`
- Request: `{ "question_id": uuid, "selected_option_ids": uuid[1..6] }`
- Validation (`422`): the question belongs to the attempt's version and has role `lesson` (`QUESTION_NOT_IN_ATTEMPT`); options are distinct and belong to the question (`INVALID_OPTIONS`); `single_choice`/`true_false` → exactly 1 option (`INVALID_SELECTION_COUNT`).
- States: attempt not `in_progress` → `409 ATTEMPT_NOT_OPEN`.
- 201: `AnswerResult` plus `"replayed": false`.
- **Idempotency**: if the question was already answered in this attempt, the response is **200** with the *stored* result and `"replayed": true`, even if the new selection differs. The first answer is final.
- Example response:
```json
{
  "question_id": "q-1",
  "is_correct": false,
  "selected_option_ids": ["opt-a"],
  "correct_option_ids": ["opt-b"],
  "option_feedback": [
    {"option_id": "opt-a", "is_correct": false, "feedback": "Testimonials from satisfied users are exactly the evidence that fits her belief."},
    {"option_id": "opt-b", "is_correct": true,  "feedback": "Comparing both conditions — ideally blind — lets evidence against the belief show up."},
    {"option_id": "opt-c", "is_correct": false, "feedback": "Counting only the hits ignores the misses."}
  ],
  "explanation": "Avoiding confirmation bias means looking for evidence that could show you're wrong.",
  "replayed": false
}
```

### `POST /attempts/{attempt_id}/complete`
- Request: `{}`
- Preconditions: every lesson question in the pinned version has been answered, otherwise `409 ATTEMPT_INCOMPLETE` with `details: [{question_id}]`. An attempt in status `abandoned` → `409 ATTEMPT_NOT_OPEN`.
- 200:
```json
{
  "attempt": { "id": "…", "status": "completed", "correct_first_try": 2, "question_count": 3, "is_first_completion": true },
  "xp_awarded": [ {"reason": "lesson_complete", "amount": 20}, {"reason": "daily_goal", "amount": 10} ],
  "xp": { "today": 45, "goal": 20, "total": 170, "daily_goal_reached_now": true },
  "streak": { "current": 4, "longest": 5, "freezes_available": 1, "done_today": true, "at_risk": false },
  "first_review_on": "2026-11-04",
  "achievements_unlocked": [ {"code": "five_lessons", "title": "Getting the picture", "description": "…", "earned_at": "…"} ],
  "next_lesson": { "...": "LessonSummary or null" },
  "replayed": false
}
```
In this example the user had 15 XP earlier that day. The 20-XP completion crossed the 20-XP goal, so the daily goal bonus was added. The bonus is not counted toward the threshold itself.
- **Idempotency**: completing an already-completed attempt → **200** with the same summary reconstructed from stored data (XP rows linked by `attempt_id` and the achievements earned at that time), `"replayed": true`. No new XP, streak change, or review scheduling occurs.

### `POST /attempts/{attempt_id}/rating`
- Request: `{ "rating": "clear" | "unclear" }`. Only allowed on completed attempts (`409 ATTEMPT_NOT_COMPLETED`).
- 204. Upserts `lesson_ratings (user, lesson_version)`.

### `POST /lessons/{slug}/feedback`
- Request: `{ "kind": "factual_error"|"unclear"|"typo"|"other", "message"?: string ≤ 500, "question_id"?: uuid, "lesson_version_id": uuid }`
- 201 `{ "id": "…" }`. Rate limit: 10/day per user. Not idempotent (each report is a new row). The client disables the submit button while the request is in flight.

---

## 5.6 Reviews

### `GET /reviews/summary`
200: `{ "due_count": 5, "next_due_on": "2026-11-04" | null, "in_review_count": 12, "open_session_id": "…" | null, "estimated_minutes": 3 }`
`due_count` is capped only by data, while sessions are capped at 20. The client shows "20+ due" when the count is above 20.

### `GET /reviews/concepts`
Query: `limit` (default 50), `cursor`. Lists the concepts in review ordered by `due_on`.
200: `{ "items": [{ "lesson": {slug, title}, "mastery_stage": 2, "due_on": "2026-11-09", "is_due": false }], "next_cursor": null }`

### `POST /review-sessions`
Create today's session or return the open one.
- Request: `{}`
- 201 (new) / 200 (existing open session for today, `"resumed": true`):
```json
{
  "session": {
    "id": "…", "status": "open", "local_date": "2026-11-03", "item_count": 3, "answered_count": 1,
    "items": [
      { "id": "item-1", "position": 1, "lesson": {"slug": "anchoring", "title": "Anchoring"},
        "question": { "id": "…", "type": "single_choice", "prompt": "…", "options": [{"id": "…", "text": "…"}] },
        "result": null }
    ]
  },
  "resumed": false
}
```
For answered items, `result` holds `ReviewAnswerResult` (below), and the question still shows the options.
- Errors: `409 NOTHING_DUE` when `due_count = 0`, with `details: [{ "next_due_on": "…" }]`.

### `GET /review-sessions/{session_id}`
200: `{ "session": … }` (same shape) plus a `summary` object once the session is completed or ended. `404 SESSION_NOT_FOUND`.

### `POST /review-sessions/{session_id}/items/{item_id}/answer`
- Request: `{ "selected_option_ids": uuid[1..6], "guessed": boolean (default false) }`
- Validation: the same option rules as lesson answers (`422`). The session must be `open` (`409 SESSION_NOT_OPEN`). The item must belong to the session (`404 ITEM_NOT_FOUND`).
- 201:
```json
{
  "result": {
    "is_correct": true, "quality": 4,
    "correct_option_ids": ["…"], "option_feedback": [ … ], "explanation": "…",
    "schedule": { "previous_interval_days": 1, "next_interval_days": 6, "next_due_on": "2026-11-09" },
    "mastery_stage": { "before": 1, "after": 2 }
  },
  "xp_awarded": [ {"reason": "review_item", "amount": 5} ],
  "session": { "answered_count": 3, "item_count": 3, "status": "completed" },
  "session_summary": {          // present only when this answer completed the session
    "correct": 2, "total": 3, "xp_total": 21,
    "advanced": [{"slug": "anchoring", "from": 1, "to": 2}],
    "to_revisit": [{"slug": "framing-effect", "title": "The framing effect"}]
  },
  "streak": { "...": "StreakOut (present when session completed)" },
  "achievements_unlocked": [],
  "replayed": false
}
```
- **Idempotency**: an item that was already answered gives **200** with the stored result and `"replayed": true`. No state changes.
- The review state is locked `FOR UPDATE`, which serialises concurrent answers for the same concept.

### `POST /review-sessions/{session_id}/end`
- Request: `{}`
- 200: `{ "session": { "status": "ended_early", "answered_count": 2, "item_count": 5 }, "summary": {…} }`
- Idempotent: ending an already ended, completed, or expired session returns its current state (200).

---

## 5.7 Progress and gamification

### `GET /progress`
200:
```json
{
  "lessons": { "total": 27, "started": 6, "completed": 5, "by_stage": {"1": 2, "2": 2, "3": 1, "4": 0} },
  "by_topic": [ { "slug": "judgment", "title": "Judging under uncertainty", "total": 9, "completed": 3 } ],
  "xp": { "total": 160, "today": 35, "goal": 20 },
  "streak": { "current": 4, "longest": 5, "freezes_available": 1, "done_today": true, "at_risk": false },
  "recall_accuracy": { "correct": 8, "total": 10 },
  "reviews": { "due_count": 0, "next_due_on": "2026-11-04" }
}
```

### `GET /achievements`
200: `{ "items": Achievement[] }`. All 8 definitions in registry order, with `earned_at` set or null.

---

## 5.8 AI explanations

### `POST /lessons/{slug}/explanations`
- Request: `{ "mode": "simpler" | "example" | "analogy", "lesson_version_id": uuid, "exclude_ids"?: uuid[≤3] }`
  - `lesson_version_id` must be the current version or the version of one of the user's open attempts (`422 VERSION_NOT_AVAILABLE`).
  - `exclude_ids` are variants the user has already seen, used by "Another version".
- Flow and limits: see [08](08-ai-explanations.md).
- 200:
```json
{
  "explanation": {
    "id": "…", "mode": "analogy", "content": "Think of anchoring like…",
    "label": "ai_generated",           // ai_generated | ai_reviewed (status=approved)
    "variant": 2, "has_more_variants": true
  },
  "usage": { "remaining_today": 7, "limit_per_day": 20 }
}
```
- Errors: `404 LESSON_NOT_FOUND`; `429 AI_RATE_LIMITED` (per-user daily or burst limit, `Retry-After`); `503 AI_UNAVAILABLE` (provider error, timeout, invalid output, or global budget exhausted, with `details.reason` ∈ `provider`, `timeout`, `quality`, `budget`); `503 AI_DISABLED` (feature flag off).
- Idempotency: safe to repeat. Cached variants are returned. Each call counts toward the user's request limit, including cache hits (prevents scraping). Cost is incurred only on generation.

### `POST /explanations/{explanation_id}/feedback`
- Request: `{ "rating": "helpful" | "not_helpful" | "incorrect" }`
- 204. Upsert per (explanation, user). An `incorrect` rating increments `flag_count` only the first time this user flags that explanation. See [08 §8.6](08-ai-explanations.md#86-feedback-and-moderation) for automatic hiding.
- Errors: `404 EXPLANATION_NOT_FOUND`. The user must have received this explanation (an `ai_requests` row exists), otherwise `404`.

---

## 5.9 Analytics events

### `POST /events`
- Request: `{ "events": [ { "name": string, "occurred_at": ISO, "properties"?: object } ] }`, with 1–20 events.
- Only whitelisted client events are accepted (see [12 §12.2](12-analytics-validation.md#122-event-catalogue)). Unknown names or properties are dropped silently and reported in the response. `occurred_at` is clamped to the range [now − 7 days, now + 5 min].
- 202: `{ "accepted": 3, "rejected": 0 }`. Rate limit 60 requests/hour per user.

---

## 5.10 Operational

| Method | Path | Auth | Response |
|---|---|---|---|
| GET | `/health` | Public | 200 `{ "status": "ok", "version": "<git sha>" }` (process liveness, no DB) |
| GET | `/health/ready` | Public | 200 `{ "status": "ready" }` / 503 if the DB is unreachable or a migration is pending |

These are mounted outside `/v1` (at `/health`) so that load balancers have a stable path.

## 5.11 Endpoint index

| Method | Path | Auth | Idempotent? |
|---|---|---|---|
| POST | /auth/guest | Public | No (client-guarded) |
| POST | /auth/register | Public | No (409 on repeat) |
| POST | /auth/upgrade | Guest | Effectively (409 on repeat) |
| POST | /auth/login | Public | Yes (new tokens each time) |
| POST | /auth/refresh | Public | Grace window |
| POST | /auth/logout | Any | Yes |
| POST | /auth/password-reset/request | Public | Yes (always 202) |
| POST | /auth/password-reset/confirm | Public | Single-use token |
| POST | /me/password | Full | No |
| GET/PATCH | /me | Any | Yes |
| GET/PATCH | /me/preferences | Any | Yes |
| GET | /me/export | Any | Yes |
| DELETE | /me | Any | Yes (401 after) |
| GET | /subjects | Any | — |
| GET | /lessons | Any | — |
| GET | /lessons/{slug} | Any | — |
| GET | /discover | Any | — |
| POST | /lessons/{slug}/attempts | Any | Yes (returns open attempt) |
| GET | /attempts/{id} | Owner | — |
| POST | /attempts/{id}/answers | Owner | Yes (first answer final) |
| POST | /attempts/{id}/complete | Owner | Yes |
| POST | /attempts/{id}/rating | Owner | Yes (upsert) |
| POST | /lessons/{slug}/feedback | Any | No (rate-limited) |
| GET | /reviews/summary | Any | — |
| GET | /reviews/concepts | Any | — |
| POST | /review-sessions | Any | Yes (returns open session) |
| GET | /review-sessions/{id} | Owner | — |
| POST | /review-sessions/{id}/items/{item_id}/answer | Owner | Yes |
| POST | /review-sessions/{id}/end | Owner | Yes |
| GET | /progress | Any | — |
| GET | /achievements | Any | — |
| POST | /lessons/{slug}/explanations | Any | Yes (cached) |
| POST | /explanations/{id}/feedback | Any | Yes (upsert) |
| POST | /events | Any | No (append-only) |
| GET | /health, /health/ready | Public | — |

"Any" = guest or full user. "Owner" = any authenticated user, but the resource must belong to them (otherwise 404).
