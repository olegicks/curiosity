# 11 — Testing Strategy and Acceptance Criteria

## 11.1 Definition of Done (every feature)

A feature is **done** only when all of the following hold:
1. Its behaviour matches the spec, including error states and edge cases, not only the happy path.
2. Data persists correctly server-side, and the relevant transactions and constraints are in place (migration included).
3. Unit tests cover the pure rules, and integration tests cover the endpoints (including authorization and idempotency).
4. The client handles loading, empty, error, and offline states for the feature.
5. Accessibility labels exist and the screen works at 200% text size in both themes.
6. CI passes: lint, types, tests, content validation, and the API type drift check.
7. Any deviation from the spec is recorded in [15](15-decisions-and-risks.md).

## 11.2 Test layers

| Layer | Tooling | Scope | Runs |
|---|---|---|---|
| Backend unit | pytest | Pure modules: scheduler, streaks, XP keys, grading, progress/mastery, recommendations, selection, content schema rules, AI guard, pricing | Every push (CI) |
| Backend integration | pytest + httpx `TestClient` + **real PostgreSQL** (Docker service in CI, docker compose locally). Each test runs in a transaction that is rolled back. Concurrency tests use separate connections. | Every endpoint, the authz matrix, idempotency, transactions, migrations up/down | Every push |
| Migration test | `alembic upgrade head` on an empty DB, then `downgrade -1`/`upgrade head`. Model and migration diff check (`alembic check`) | Schema drift | Every push |
| Content | `curiosity content validate content/` plus an import into a fresh DB | All lessons | Every push |
| Contract | Regenerate `schema.d.ts`, `git diff --exit-code` | API ↔ client | Every push |
| Mobile unit/component | Jest + React Native Testing Library, with the API mocked (MSW or fetch mock) | UI components, hooks, player step machine, error mapping, token refresh | Every push |
| E2E | **Maestro** flows on an iOS simulator and an Android emulator against a local API, seeded content, and `FakeProvider` | Primary journeys | Before each release (manual trigger in CI if macOS runners are available, otherwise locally) |
| Manual QA | Checklist in `docs/qa-checklist.md` (to be written) on one physical iPhone and one physical Android device | Visual, haptics, accessibility, offline | Before each store submission |

**Time control:** all time-dependent logic receives a `Clock`. Tests use `FixedClock` and advance days explicitly. No test sleeps.
**Coverage target:** ≥ 90% line coverage for pure domain modules and ≥ 80% overall backend. Coverage is a guide, not a goal in itself.

## 11.3 Required test cases (minimum set)

### Auth and isolation
- T-AUTH-1 guest creation returns tokens. `GET /me` shows `is_guest=true`.
- T-AUTH-2 upgrade keeps `user.id`, progress, XP, and streak. Old refresh tokens are rejected afterwards.
- T-AUTH-3 login with a wrong password or an unknown email returns an identical 401 body.
- T-AUTH-4 refresh rotation. Reuse outside the grace window revokes the family. Reuse inside the grace window returns the successor.
- T-AUTH-5 password reset invalidates existing access tokens (via `token_version`) and refresh tokens.
- T-AUTH-6 rate limit on login returns 429 with `Retry-After`.
- T-AUTH-7 **authorization matrix**: for every owner-scoped endpoint (attempts, answers, complete, rating, sessions, items, end, explanation feedback), user B gets 404 for A's resource and A's rows are unchanged.
- T-AUTH-8 guest calling `/me/password` returns 403 `FULL_ACCOUNT_REQUIRED`.

### Content
- T-CNT-1 only published lessons appear in lists, details, and discover. Draft and retired lessons return 404.
- T-CNT-2 lesson detail and attempt responses contain no `is_correct`/`feedback` keys (schema-level assertion over the JSON).
- T-CNT-3 validator rejects each rule violation in §3.3 (one fixture per rule).
- T-CNT-4 import is idempotent (a second run is a no-op). Changed content without a version bump fails. A version bump creates a new version, and open attempts stay pinned to the old version.

### Lessons
- T-LRN-1 start → 201. A repeat start returns 200 with the same attempt. A concurrent double start yields one attempt.
- T-LRN-2 answer grading is correct for single, multi (all-or-nothing, including a subset and a superset), and true/false.
- T-LRN-3 invalid options, options from another question, or a question not in the attempt return 422.
- T-LRN-4 answer replay returns the stored result even with a different selection.
- T-LRN-5 completion with unanswered questions returns 409 with the list.
- T-LRN-6 **completion updates progress exactly once**: completing the same attempt twice (sequentially and concurrently) gives one `first_completed_at`, one review state, one `lesson_complete` XP row, and a single streak increment.
- T-LRN-7 revisit attempt: completion grants no XP and leaves the review state untouched, while `completion_count` increments and the streak day counts.
- T-LRN-8 perfect bonus is only granted on the first completion with all answers correct.

### Reviews and scheduling
- T-REC-1 scheduler unit tests reproduce **every row** of the worked example table ([07 §7.3.5](07-learning-engine.md#735-worked-examples-these-become-unit-test-fixtures)) plus the edge fixtures (EF floor, interval cap, growth guard).
- T-REC-2 the quality mapping is correct (incorrect→1, guessed→3, correct→4).
- T-REC-3 a **failed review** resets reps to 0, sets interval 1, `due_on = today+1`, increments lapses, and lowers EF by 0.20 with clamping.
- T-REC-4 due calculation: an item is due exactly when `due_on ≤ local_today` in the user's timezone (tests around midnight in `Pacific/Auckland` and `America/Los_Angeles`). `GET /reviews/summary` count = session item count (≤ 20).
- T-REC-5 session creation is idempotent per day. A stale open session from yesterday is expired and replaced.
- T-REC-6 answering is idempotent. Concurrent answers to the same item produce one event and one state change.
- T-REC-7 the session auto-completes on the last answer and awards session XP once. `end` leaves unanswered items due.
- T-REC-8 question selection excludes the last question shown when alternatives exist, and never uses `lesson`-role questions.
- T-REC-9 milestones: `first_recalled_at` is set on the first success, and `first_understood_at` when reps reach 2. A later failure does not clear milestones but lowers `mastery_stage`.

### Gamification
- T-GAM-1 XP idempotency: replaying every XP-awarding request N times leaves the totals unchanged (property-style test over the endpoints).
- T-GAM-2 daily goal bonus is awarded once per local day, at the threshold crossing.
- T-GAM-3 streak transitions: consecutive days, same day, a 1-day gap covered by a freeze, a 3-day gap with 1 freeze resets to 1, freeze earned at 7 and capped at 2, display logic.
- T-GAM-4 achievements are unlocked once, on the correct triggers.

### AI
- T-AI-1 a cache hit returns the stored explanation without calling the provider (FakeProvider call count = 0).
- T-AI-2 per-user daily and burst limits return 429 and record a `rate_limited` row.
- T-AI-3 global budget exhausted returns 503 `AI_UNAVAILABLE` (reason budget) without a provider call.
- T-AI-4 provider timeout or error returns 503, and **lesson endpoints keep working** in the same test (start/answer/complete succeed while the provider is failing).
- T-AI-5 guard rejects outputs with URLs, invented numbers, headings, or the wrong length (unit tests with fixture texts).
- T-AI-6 variant ceiling: after 3 variants no further provider calls occur.
- T-AI-7 two flags from distinct users hide a `generated` explanation.
- T-AI-8 the provider key never appears in logs or responses (log capture assertion).

### Privacy
- T-PRIV-1 `DELETE /me` removes every user-owned row (assert a zero count in each table listed in [09 §9.6](09-security-privacy.md#96-account-deletion)). `ai_requests` and `content_feedback` rows remain with `user_id` NULL.
- T-PRIV-2 after deletion, the access and refresh tokens return 401.
- T-PRIV-3 export contains all categories and no other user's data.
- T-PRIV-4 guest purge deletes only guests inactive for more than 30 days.

### Mobile and E2E (Maestro)
- E2E-1 first run: Welcome → guest → onboarding skip → lesson → answer all → complete → Discover shows "1 of N".
- E2E-2 review: seed a user with a due concept (backend test-seed CLI) → Recall → answer → summary.
- E2E-3 AI: open the explanation sheet → FakeProvider text shows with the AI badge. With the provider forced to fail → error copy, and the lesson continues.
- E2E-4 upgrade account, then logout and login → progress retained.
- E2E-5 delete account → back to Welcome. Logging in with the old credentials fails.
- E2E-6 offline: airplane mode during a lesson → banner, Check disabled. Reconnect → continue.
- Each runs on iOS (latest-1 major and latest) and Android (API 29 and the latest) emulators.

## 11.4 Feature-level acceptance criteria

### Accounts and onboarding
- **AC-AUTH-1** A new user reaches the first lesson's step 1 in ≤ 3 taps from Welcome without entering any personal data.
- **AC-AUTH-2** A guest can upgrade and keeps 100% of their progress (same user ID). Verified by T-AUTH-2 and E2E-4.
- **AC-AUTH-3** Passwords are stored only as argon2id hashes, and tokens are stored only hashed. Verified by a DB inspection test.
- **AC-AUTH-4** No endpoint returns or modifies another user's private data (T-AUTH-7 is green).
- **AC-AUTH-5** Password reset works end-to-end in staging with the real email provider.
- **AC-ONB-1** Onboarding steps are skippable and shown once per account.

### Discover
- **AC-DISC-1** The primary action follows the documented priority for each of the 4 cases (integration test per case, plus a component test per case).
- **AC-DISC-2** Discover renders from one API call. P95 server time is ≤ 300 ms at seeded scale (27 lessons, 200 review states).
- **AC-DISC-3** Streak, today's XP vs goal, due count, and progress match `/progress` and `/reviews/summary`.

### Lesson player
- **AC-LRN-1** All published lessons render every step type in both themes at 100% and 200% text size without clipping (snapshot or visual check across all lessons in the manual QA run).
- **AC-LRN-2** Answers are graded only by the server. Correct options are absent from all responses before answering (T-CNT-2).
- **AC-LRN-3** Feedback shows correctness, the selected option's feedback, and the explanation, with icon + text + colour.
- **AC-LRN-4** Completion updates progress, schedules the first review for tomorrow, and awards XP **exactly once** (T-LRN-6).
- **AC-LRN-5** Leaving and returning resumes the same attempt with prior answers shown.
- **AC-LRN-6** The completion screen offers a related next lesson when one exists.

### Recall
- **AC-REC-1** Due items are computed consistently in the user's timezone, and the summary count equals session items (up to 20).
- **AC-REC-2** Intervals follow §7.3 exactly (T-REC-1..3).
- **AC-REC-3** Review questions are never the lesson's own questions.
- **AC-REC-4** The session can be finished or ended early. Answered items persist, and unanswered ones stay due.
- **AC-REC-5** Feedback after each item shows the explanation, the next review timing, and the mastery change.

### AI explanations
- **AC-AI-1** All three modes return labeled explanations that are visually distinct from lesson content.
- **AC-AI-2** AI failure or disablement never blocks lesson or review flows (T-AI-4, E2E-3).
- **AC-AI-3** Per-user and global limits are enforced (T-AI-2, T-AI-3). Cost is recorded for every provider call.
- **AC-AI-4** API keys exist only in backend secrets. The mobile bundle contains no provider strings (CI grep on the built JS bundle for `sk-ant` and `anthropic`).

### Gamification
- **AC-GAM-1** XP rules match §7.4. Replays never duplicate XP (T-GAM-1).
- **AC-GAM-2** Streak and freeze behaviour matches §7.5 (T-GAM-3).
- **AC-GAM-3** The 8 achievements unlock on their exact conditions, once.

### Privacy and operations
- **AC-PRIV-1** Account deletion is reachable in ≤ 3 taps from Profile and deletes data as documented (T-PRIV-1, E2E-5).
- **AC-PRIV-2** Export works for guests and full users.
- **AC-OPS-1** `docker compose up` gives a working local API with seeded content in ≤ 5 minutes on a clean machine, following the README.
- **AC-OPS-2** A deployment runs migrations and the content import automatically and fails safely (the old version keeps serving) if either fails.

### Content
- **AC-CNT-1** At least 20 lessons are published at launch. Every one has passed the editorial checklist, which is recorded in the PR, and has ≥ 2 sources and ≥ 4 recall questions.
- **AC-CNT-2** "Report a problem" reports are stored and listable via the CLI.
