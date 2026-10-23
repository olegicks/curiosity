# 04 — Data Model

PostgreSQL 16+. All tables are managed by Alembic migrations generated from SQLAlchemy 2.0 models and reviewed by hand. Naming: `snake_case`, plural table names, `id` primary keys of type `uuid` (UUIDv7, generated in the application) unless a composite key is more natural. Every table has `created_at timestamptz not null default now()`. Mutable tables also have `updated_at`.

Enums are stored as `text` with `CHECK` constraints, not native PG enums, which keeps migrations cheap. Python `StrEnum`s mirror them.

## 4.1 Entity overview

```
users 1─1 user_preferences
users 1─* user_topic_interests *─1 topics
users 1─* refresh_tokens, password_reset_tokens
subjects 1─* topics 1─* lessons 1─* lesson_versions 1─* questions 1─* answer_options
lessons 1─1 lesson_versions (current_version_id)
lesson_versions *─* sources            (lesson_version_sources)
lessons *─* lessons                    (lesson_relations)
users 1─* lesson_attempts 1─* lesson_attempt_answers
users 1─* user_lesson_progress *─1 lessons
users 1─* review_states *─1 lessons
users 1─* review_sessions 1─* review_session_items 1─0..1 review_events
users 1─* xp_transactions, daily_activity, user_achievements
users 1─1 streak_states
lesson_versions 1─* ai_explanations 1─* ai_explanation_feedback
users 0..1─* ai_requests
users 0..1─* content_feedback
users 1─* product_events
```

## 4.2 Identity and preferences

### `users`
Purpose: the account, either guest or full.

| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | |
| `email` | text null | Unique when not null. Null for guests. Stored lowercase-trimmed, enforced by `CHECK (email = lower(email))` (see 15 §15.6, DEV-1). |
| `password_hash` | text null | argon2id encoded string. |
| `display_name` | text null | ≤ 40 chars. |
| `is_guest` | bool not null | |
| `is_internal` | bool not null default false | Staff and test accounts, excluded from metrics. |
| `token_version` | int not null default 0 | Incremented to invalidate all access tokens (password change/reset, deletion). |
| `last_seen_at` | timestamptz null | Updated at most once per hour per user. Used for guest purge. |
| `upgraded_at` | timestamptz null | When the guest became a full account. |
| `created_at`, `updated_at` | timestamptz | |

Constraints: `CHECK (is_guest OR (email IS NOT NULL AND password_hash IS NOT NULL))`; `CHECK (NOT is_guest OR (email IS NULL AND password_hash IS NULL))`; unique index on `email`.
Index: `(is_guest, last_seen_at)` for the guest purge.

### `user_preferences`
| Column | Type | Notes |
|---|---|---|
| `user_id` | uuid PK FK→users ON DELETE CASCADE | |
| `timezone` | text not null default 'UTC' | Validated against `zoneinfo.available_timezones()`. |
| `daily_xp_goal` | smallint not null default 20 | `CHECK (daily_xp_goal IN (20,40,60))` |
| `onboarding_completed_at` | timestamptz null | |
| `updated_at` | timestamptz | |

### `user_topic_interests`
PK `(user_id, topic_id)`. FK user → CASCADE. FK topic → CASCADE. Max 3 per user, enforced in the service.

### `refresh_tokens`
| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | |
| `user_id` | uuid FK CASCADE | |
| `family_id` | uuid not null | All rotations from one login share a family. |
| `token_hash` | bytea not null unique | SHA-256 of the 256-bit random token. The raw token is never stored. |
| `expires_at` | timestamptz not null | 30 days from issue. |
| `rotated_at` | timestamptz null | Set when exchanged for a new token. |
| `revoked_at` | timestamptz null | |
| `created_at` | timestamptz | |

Indexes: `(user_id)`, `(family_id)`. Reuse of a rotated token revokes the whole family (see [09](09-security-privacy.md)).

### `password_reset_tokens`
`id`, `user_id` FK CASCADE, `token_hash` bytea unique, `expires_at` (30 min), `used_at` null, `created_at`. Index `(user_id)`.

## 4.3 Content

### `subjects`
`id` uuid PK, `slug` text unique, `title`, `description`, `position` int, `is_published` bool.

### `topics`
`id` uuid PK, `subject_id` FK→subjects RESTRICT, `slug` text, `title`, `description`, `position` int. Unique `(subject_id, slug)`.

### `lessons`
Purpose: the stable identity of a concept/lesson across versions.

| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | From the content file. |
| `slug` | text unique not null | |
| `topic_id` | uuid FK→topics RESTRICT | |
| `position` | int not null | |
| `status` | text | `draft` \| `published` \| `retired` |
| `current_version_id` | uuid null FK→lesson_versions (DEFERRABLE INITIALLY DEFERRED) | The published version that users see. |
| `created_at`, `updated_at` | | |

Index: `(topic_id, position)`. `CHECK (status <> 'published' OR current_version_id IS NOT NULL)`.

### `lesson_versions`
Purpose: an immutable content snapshot.

| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | |
| `lesson_id` | uuid FK→lessons CASCADE | |
| `version` | int not null | Unique `(lesson_id, version)`. |
| `title`, `description`, `learning_objective` | text | |
| `estimated_minutes` | smallint | |
| `evidence_status` | text | `established` \| `mixed` \| `contested` |
| `body` | jsonb not null | Ordered `steps` (validated by the content schema). Question steps hold `question_key`. |
| `content_hash` | char(64) not null | |
| `last_reviewed_on` | date null | |
| `reviewers` | text[] not null default '{}' | |
| `published_at` | timestamptz null | |
| `created_at` | | |

**Why JSONB for steps:** steps are rendered as a document, versioned as a whole, never queried by field, and validated by Pydantic. Questions and options are normalised separately because answers, reviews and analytics reference them.

### `questions`
| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | |
| `lesson_version_id` | uuid FK CASCADE | |
| `key` | text | Unique `(lesson_version_id, key)`. |
| `role` | text | `lesson` \| `recall` |
| `type` | text | `single_choice` \| `multi_select` \| `true_false` |
| `prompt` | text | |
| `explanation` | text | |
| `shuffle` | bool | |
| `position` | smallint | |

Index: `(lesson_version_id, role)`.

### `answer_options`
`id` uuid PK, `question_id` FK CASCADE, `key` text, `text`, `is_correct` bool, `feedback` text, `position` smallint. Unique `(question_id, key)`. The rules on the number of correct options per question type are enforced by the content validator, not the DB, because they span rows.

### `sources`
`id` uuid PK, `key` text unique, `type` text CHECK, `citation` text, `doi` text null, `url` text null, `peer_reviewed` bool.

### `lesson_version_sources`
PK `(lesson_version_id, source_id)`. FK version CASCADE, source RESTRICT. Also `note` text null and `position` smallint.

### `lesson_relations`
PK `(from_lesson_id, to_lesson_id, relation_type)`. `relation_type` ∈ `related`, `prerequisite`. Also `position` smallint. `CHECK (from_lesson_id <> to_lesson_id)`. Both FKs CASCADE.

## 4.4 Learning activity

### `lesson_attempts`
| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | |
| `user_id` | uuid FK→users CASCADE | |
| `lesson_id` | uuid FK→lessons RESTRICT | |
| `lesson_version_id` | uuid FK→lesson_versions RESTRICT | Pinned at start. |
| `status` | text | `in_progress` \| `completed` \| `abandoned` |
| `is_first_completion` | bool not null default false | Set at completion. |
| `correct_first_try` | smallint null | Set at completion. |
| `question_count` | smallint not null | Number of lesson questions in the pinned version. |
| `started_at` | timestamptz not null | |
| `completed_at` | timestamptz null | |
| `local_date_completed` | date null | |

Constraints and indexes:
- Partial unique `(user_id, lesson_id) WHERE status = 'in_progress'`: at most one open attempt per lesson.
- Partial unique `(user_id, lesson_id) WHERE is_first_completion`: only one attempt can be the first completion, which also guards XP.
- Index `(user_id, started_at DESC)`.
- `CHECK ((status = 'completed') = (completed_at IS NOT NULL))`.

### `lesson_attempt_answers`

D-18 (migration 0008): adds `value double precision null` (estimate answers; `selected_option_ids` is then empty), and `questions` gains `estimate jsonb null` with `type` allowing `estimate`.
| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | |
| `attempt_id` | uuid FK CASCADE | |
| `question_id` | uuid FK→questions RESTRICT | Must belong to the attempt's version and have role `lesson` (enforced in the service). |
| `selected_option_ids` | uuid[] not null | Validated: non-empty, distinct, all belong to the question. |
| `is_correct` | bool not null | |
| `answered_at` | timestamptz | |

Unique `(attempt_id, question_id)` gives exactly one scored answer per question per attempt.
*Trade-off:* `uuid[]` instead of a join table. The options are validated in the service and never queried relationally. This is simpler and keeps the history accurate.

### `user_lesson_progress`
Purpose: milestone summary per user and lesson.

| Column | Type | Notes |
|---|---|---|
| `user_id` | uuid FK CASCADE | PK part |
| `lesson_id` | uuid FK RESTRICT | PK part |
| `first_started_at` | timestamptz not null | |
| `first_completed_at` | timestamptz null | |
| `first_recalled_at` | timestamptz null | |
| `first_understood_at` | timestamptz null | |
| `completion_count` | int not null default 0 | |
| `first_attempt_score` | smallint null | Correct-first-try count of the first completion. |
| `last_activity_at` | timestamptz not null | |

Index: `(user_id, first_completed_at)`. CHECKs enforce milestone ordering (completed ≥ started, etc.).

## 4.5 Reviews

### `review_states`
Purpose: the current schedule for each user and concept.

| Column | Type | Notes |
|---|---|---|
| `user_id` | uuid FK CASCADE | PK part |
| `lesson_id` | uuid FK RESTRICT | PK part |
| `scheduler_version` | text not null | e.g. `sm2-curiosity-v1` |
| `ease_factor` | numeric(3,2) not null | CHECK 1.30–2.80 |
| `interval_days` | int not null | CHECK 1–180 |
| `repetitions` | int not null | CHECK ≥ 0 |
| `lapses` | int not null | CHECK ≥ 0 |
| `due_on` | date not null | |
| `last_reviewed_at` | timestamptz null | |
| `last_question_id` | uuid null FK→questions SET NULL | |
| `created_at`, `updated_at` | | |

Index: `(user_id, due_on)` for due queries.

### `review_sessions`
| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | |
| `user_id` | uuid FK CASCADE | |
| `local_date` | date not null | Local date at creation. |
| `status` | text | `open` \| `completed` \| `ended_early` \| `expired` |
| `item_count` | smallint not null | |
| `created_at`, `completed_at` | | |

Partial unique `(user_id) WHERE status = 'open'`. Index `(user_id, created_at DESC)`.

### `review_session_items`
`id` uuid PK, `session_id` FK CASCADE, `lesson_id` FK RESTRICT, `question_id` FK RESTRICT, `position` smallint, `answered_at` timestamptz null. Unique `(session_id, lesson_id)` and unique `(session_id, position)`.

### `review_events` (review history)
| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | |
| `user_id` | uuid FK CASCADE | |
| `session_item_id` | uuid unique FK→review_session_items CASCADE | One answer per item. |
| `lesson_id`, `question_id` | uuid | |
| `selected_option_ids` | uuid[] | |
| `is_correct` | bool | |
| `guessed` | bool | |
| `quality` | smallint | CHECK IN (1,3,4) |
| `scheduler_version` | text | |
| `ef_before`, `ef_after` | numeric(3,2) | |
| `interval_before`, `interval_after` | int | `interval_before` = the scheduled interval being tested. |
| `reps_before`, `reps_after` | int | |
| `due_on_before`, `due_on_after` | date | |
| `days_since_last_review` | int | Actual gap since the previous review, or since first completion. |
| `review_number` | int | 1-based count of reviews for this user and concept. |
| `local_date` | date | |
| `answered_at` | timestamptz | |

Indexes: `(user_id, answered_at DESC)` (recent accuracy, export), `(lesson_id, question_id)` (item analysis).

## 4.6 Gamification

### `xp_transactions`
| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | |
| `user_id` | uuid FK CASCADE | |
| `amount` | int not null | CHECK > 0 |
| `reason` | text | `lesson_complete` \| `lesson_perfect` \| `review_item` \| `review_session` \| `daily_goal` |
| `idempotency_key` | text not null | See [07 §7.4](07-learning-engine.md#74-xp-rules). |
| `lesson_id` | uuid null | |
| `attempt_id` | uuid null | |
| `review_session_id` | uuid null | |
| `local_date` | date not null | |
| `created_at` | | |

**Unique `(user_id, idempotency_key)`**. Index `(user_id, local_date)`.

### `streak_states`
PK `user_id` FK CASCADE; `current_streak` int, `longest_streak` int, `last_streak_date` date null, `freezes_available` smallint CHECK 0–2 default 1, `freezes_used_total` int, `updated_at`. Created lazily on the first qualifying event (see 15 §15.6, DEV-4).

### `daily_activity`
PK `(user_id, local_date)`; `lesson_questions_answered`, `review_items_answered`, `lessons_completed`, `review_sessions_completed`, `xp_earned` (all int ≥ 0), `updated_at`. Index `(local_date)` for cohort queries.

### `user_achievements`
PK `(user_id, code)`; `earned_at`. `code` is validated against the code registry in the service.

## 4.7 AI

### `ai_explanations` (shared cache)
| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | |
| `lesson_version_id` | uuid FK CASCADE | |
| `mode` | text | `simpler` \| `example` \| `analogy` |
| `variant` | smallint | 1..`AI_MAX_VARIANTS` (3) |
| `prompt_version` | text | e.g. `explain-v1` |
| `model` | text | |
| `content` | text | ≤ 1,500 chars after validation. |
| `status` | text | `generated` \| `approved` \| `hidden` \| `rejected` |
| `flag_count` | int default 0 | Count of "incorrect" flags. |
| `input_tokens`, `output_tokens` | int | |
| `cost_micros` | bigint | |
| `created_at`, `reviewed_at` | | |

Unique `(lesson_version_id, mode, prompt_version, variant)`. Index `(lesson_version_id, mode, status)`.

### `ai_requests` (usage log, one row per user request)
| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | |
| `user_id` | uuid null FK→users SET NULL | Kept anonymised after account deletion for cost accounting. Holds no content. |
| `lesson_version_id` | uuid | |
| `mode` | text | |
| `explanation_id` | uuid null | |
| `outcome` | text | `cache_hit` \| `generated` \| `rate_limited` \| `budget_exceeded` \| `disabled` \| `provider_error` \| `timeout` \| `invalid_output` |
| `model` | text null | |
| `input_tokens`, `output_tokens` | int default 0 | |
| `cost_micros` | bigint default 0 | Non-zero only for provider calls (including failed calls that were billed). |
| `latency_ms` | int | |
| `created_at` | timestamptz | |

Indexes: `(user_id, created_at)` for per-user daily limits, `(created_at)` for the global budget and cost metrics.

### `ai_explanation_feedback`
PK `(explanation_id, user_id)` (one rating per user, overwritable); `rating` ∈ `helpful`, `not_helpful`, `incorrect`; `created_at`. User FK CASCADE.

## 4.8 Feedback and analytics

### `content_feedback`
`id`, `user_id` null FK SET NULL, `lesson_id` FK, `lesson_version_id` FK, `question_id` null, `kind` ∈ `factual_error`, `unclear`, `typo`, `other`; `message` text ≤ 500 null; `status` ∈ `open`, `resolved`, `dismissed`; `resolution_note`; `created_at`, `resolved_at`. Index `(status, created_at)`.
On account deletion the `message` is kept (editorially useful) but unlinked from the user. The privacy policy states this (D-15).

### `lesson_ratings`
PK `(user_id, lesson_version_id)`; `rating` ∈ `clear`, `unclear`; `created_at`. User FK CASCADE.

### `product_events`
`id` bigint identity PK, `user_id` FK CASCADE, `name` text, `properties` jsonb (≤ 2 KB, whitelisted keys), `occurred_at` timestamptz, `received_at`, `local_date` date, `platform` text (`ios`/`android`), `app_version` text. Indexes `(name, occurred_at)`, `(user_id, occurred_at)`.

## 4.9 Transaction and consistency rules

| Operation | Transaction contents | Concurrency guard |
|---|---|---|
| Start attempt | Upsert progress (`first_started_at`), insert attempt | Partial unique on open attempt. On conflict, return the existing attempt. |
| Submit lesson answer | Insert answer, upsert daily activity | Unique `(attempt_id, question_id)`. On conflict, return the stored answer. |
| Complete attempt | `SELECT attempt FOR UPDATE` → validate all answered → set completed → progress milestones → review state (first time) → XP (ON CONFLICT DO NOTHING) → streak (`SELECT streak_states FOR UPDATE`) → daily activity → achievements | Row lock plus the unique first-completion index plus XP uniqueness |
| Create review session | Expire stale open session, select due states, insert session and items | Partial unique open session. On conflict, re-read and return the open session. |
| Answer review item | Lock the review state and the item → event → state → progress → XP → streak (if the session completes) → achievements | Unique `session_item_id` on events, row locks |
| Delete account | `DELETE FROM users WHERE id = ?` (cascades), plus nulling of SET NULL references | Single statement |

Isolation level: `READ COMMITTED` with the explicit row locks above. The XP and streak updates in a request touch rows in a fixed order (attempt/item → review_state → progress → streak → daily_activity) to avoid deadlocks.
