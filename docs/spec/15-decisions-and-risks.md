# 15 — Decisions Requiring Approval, Assumptions, Risks and Dependencies

## 15.1 Decisions requiring approval before implementation

> **Status: all recommendations D-1 to D-15 approved by the product owner on 2026-10-18.**

Each decision has a **recommendation**, which the rest of the spec already assumes. Approving the recommendation needs no spec change. Choosing an alternative requires updating the referenced sections.

| ID | Decision | Recommendation (assumed in spec) | Alternatives | Affects |
|---|---|---|---|---|
| **D-1** | How users first enter the app | **Guest-first**: a server-side anonymous account is created on "Start learning", with an optional upgrade to email + password that keeps all progress | (a) Sign-up required before the first lesson: simpler data model, more friction. (b) Local-only progress until sign-up: breaks "backend authoritative" and complicates merging. | 01, 02, 04, 05, 09 |
| **D-2** | Credentials and email | **Email + password only**. Social login deferred. Transactional email provider for password reset (e.g. Postmark, Resend, Amazon SES; pick one). | Add Sign in with Apple + Google now (more setup, Apple rules). Magic-link email login instead of passwords. | 05, 09, 13 |
| **D-3** | Lesson vs concept | **One lesson = one concept** (1:1). Reviews are keyed on the lesson. | A separate `concepts` table with many lessons per concept (more flexible, extra complexity now). | 03, 04, 07 |
| **D-4** | Review grading signals | **Objective correctness plus an optional "I'm guessing" toggle** (q = 1/3/4). The concept label is shown on review items. | (a) Correctness only (q = 1/4). (b) A 3-point confidence prompt after each answer. (c) Hide the concept label to test identification too (harder, mixes two skills). | 02, 07, 12 |
| **D-5** | Content source of truth | **YAML files in the Git repo**, validated in CI and imported at deploy. No admin UI. | Headless CMS (cost, another service). Admin UI (build effort). | 03, 13 |
| **D-6** | AI model and serving policy | `AI_MODEL=claude-opus-5-5` (current default model) at low effort. **Shared cache across users**, max 3 variants per lesson-mode. Unreviewed explanations shown with a clear "AI-generated" label. Optional pre-generation plus editor approval. Guests get the same limits as full accounts. | A cheaper model such as `claude-haiku-5-5`, after a side-by-side quality check. Serve **only** editor-approved explanations (no live generation: safest, but stale for new versions). AI for full accounts only. | 08, 13 |
| **D-7** | Hosting | A container PaaS with managed Postgres and cron (e.g. Fly.io, Render, Railway), single API instance | Cloud provider (AWS ECS/RDS, GCP Cloud Run/Cloud SQL): more control, more ops | 13 |
| **D-8** | Streak forgiveness | Automatic freezes: start with 1, +1 per 7-day streak, max 2 | No freezes (stricter). Weekly "rest day" allowance. | 07 |
| **D-9** | XP values and goals | Lesson 20 (+5 perfect), review 5/1, session 10, daily goal 10. Goals 20/40/60 XP. | Tune after beta | 07 |
| **D-10** | Supported platforms | iOS and Android **phones**, current and previous OS major versions. No tablet layouts, no web. | Include web (Expo web) at extra QA cost | 01, 11 |
| **D-11** | Analytics and crash reporting | **In-house events in Postgres** (no third-party analytics). **Sentry** for crashes and errors, with PII scrubbing. | No Sentry (platform logs only). Third-party product analytics (PostHog, etc.), which adds a data processor. | 09, 12, 13 |
| **D-12** | Validation thresholds and decision rules | D7 ≥ 20%, review completion ≥ 50%, recall ≥ 70% at intervals ≥ 14 days, AI cost ≤ USD 0.10 per MAL, activation ≥ 60%. Decision rules as in 12 §12.4. | Owner-defined values | 12 |
| **D-13** | Editorial roles | Owner (or a contracted writer) authors lessons. **An independent reviewer with a psychology background** checks each lesson before publication. | Single-person authoring with a self-review delay (weaker accuracy guarantee) | 03 |
| **D-14** | Backend concurrency model | **Synchronous** SQLAlchemy + threadpool | Async SQLAlchemy + asyncpg (more complex, and the benefit only shows at higher concurrency) | 06 |
| **D-15** | Retention and deletion semantics | Guest accounts purged after 30 days of inactivity. Content-feedback messages and AI usage rows are kept unlinked after deletion. Backups ≤ 14 days. | Delete feedback messages on account deletion. Longer or shorter guest retention. | 04, 09 |

### Decisions made after v1.0

| ID | Decision | Chosen (owner, 2026-10-22) | Rejected for now | Affects |
|---|---|---|---|---|
| **D-16** | Visual direction and home screen | **Playful, game-like UI on the existing API.** The home tab is a learning **path**: one unit per topic in curated order, each lesson a node (done / current / upcoming) with a "Start" marker on the current one and a review node when concepts are due. Tabs become Path, Recall, Profile; the separate Learn library and Discover screens are replaced by the path. Bright palette with a colour per unit, bold sans type, chunky 3D buttons, icons (`@expo/vector-icons`), a stronger lesson player (thick progress bar, step-type badges, coloured feedback panel) and a celebratory completion screen with a short confetti burst (off when the OS reduces motion). The welcome screen explains the loop: learn → check → recall. No server changes. | Hearts or lives, leagues, and a mascot (the owner kept them out of the first redesign; lives would also need server rules). | 02 §2.1, §2.5, §2.6; 10 §10.1–10.3 |
| **D-17** | Several subjects, one roadmap each | Psychology, Science, Math and Economics to start; Politics listed as coming soon. Each subject has its own path (one unit per topic). The learner picks a subject in onboarding and switches from the path header. The chosen subject is a device preference (AsyncStorage), like the theme; streak, XP and recall stay global. `GET /lessons?subject=` filters by subject. Demo lessons live in `demo-content/` for local testing only. | Per-subject streaks and XP; storing the chosen subject on the server. | 02, 03, 05 |
| **D-18** | Estimate questions | New question type `estimate`: the learner picks a number on a slider and the server grades it within a tolerance. Lesson questions only for now (reviews keep option questions). New first-run tour, lesson card on node tap, mascot and reward screen are client-only. | Estimate questions in recall; free-text numeric input. | 03, 04, 05 |

## 15.2 Explicit assumptions

1. A small team (one developer with AI assistance, plus content help) builds and runs the MVP. Hence no admin UI, single instance, and CLI tooling.
2. English only. Content and UI copy are written in English.
3. Initial scale: ≤ 5,000 registered users and ≤ 500 daily active users. A single API instance and a small managed Postgres are enough.
4. Users are 16+ (store age rating "12+" or "Teen", with no data collection aimed at children). The age gate is handled by store ratings, and the app doesn't collect age.
5. "Daily learning target" is expressed in XP, not minutes, because time spent can't be measured reliably.
6. "Viewed" means *attempt started*. Passive viewing of the lesson intro is not tracked server-side.
7. Only a lesson's current published version is served to new attempts. Old versions stay for history.
8. All lessons are free. No content gating.
9. The repository owner performs all `git push`, store submissions, and production secret management.

## 15.3 Ambiguities in the brief and how they were resolved

| Brief says | Ambiguity | Resolution in this spec |
|---|---|---|
| "Featured lesson or daily learning recommendation" | Editorially featured vs personalised | Personalised "Today's lesson" from deterministic rules (07 §7.8). No editorial featuring in the MVP. |
| "Optional supporting illustrations" | Who produces them | Optional per lesson. At most ~10 lessons need a diagram at launch (dependency on an illustrator or designer, R-1). |
| "Adjust the next review interval based on the user's answer" | Grades from objective questions only? | Quality mapping with an optional guessing flag (D-4). |
| "Mastery estimates" | Probability model vs simple level | A transparent 0–4 stage from the review state, plus recent accuracy (07 §7.2). |
| "Request limits" for AI | Per user, per request, or global | Per-user daily and burst limits plus a global daily spend cap (08 §8.5). |
| "Basic learning preferences" | Which preferences | Interests (topic ordering) and daily goal only. Theme is a device setting. |
| "Data deletion functionality" | Which data survives | 09 §9.6 table plus D-15. |
| "Supported mobile platforms" | Which OS versions | D-10. |

## 15.4 Risks

| ID | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R-1 | **Content production is the critical path**: 20–27 high-quality, sourced, reviewed lessons with 6–10 questions each, plus some illustrations | High | High | Start content work in parallel with engineering. Launch gate at 20 lessons. AI-assisted drafting with mandatory human checklist review. |
| R-2 | Candidate sources in 03 §3.6 come from memory and may contain citation errors | Medium | Medium | Editors verify every source (DOI lookup) before publishing. The checklist requires it. |
| R-3 | Multiple-choice tests recognition more than free recall, which may overstate retention | High | Medium | Scenario and distinction questions. Plausible distractors. Reported with a chance-level caveat. The free-text path is deferred with a clear trigger. |
| R-4 | Small recall pools (4–6 questions per concept) let users memorise items rather than concepts | Medium | Medium | Random selection excluding the last item. Item-level analysis (M8). Expand pools for concepts that reach long intervals. |
| R-5 | AI output adds incorrect claims | Medium | Medium | Grounded prompt, output guard, labels, flagging and auto-hide, optional pre-approval, kill switch |
| R-6 | Contested science is presented as settled (e.g. loss aversion magnitude, Dunning–Kruger, dual-process) | Medium | High (credibility) | Evidence status field, evidence steps, checklist items, excluded replication-failure topics |
| R-7 | Timezone edge cases (travel, DST, manual changes) cause odd streak or due behaviour | Medium | Low | Local-date semantics fully specified. Tests around midnight and DST. A one-day tolerance is accepted. |
| R-8 | No email verification, so typos block password reset | Low | Medium | Email confirmation field on the client at upgrade. Support contact in About. |
| R-9 | Synchronous AI calls tie up threadpool threads. The in-process rate limiter is per worker or instance. | Low (at MVP scale) | Medium | 15 s timeout, threadpool sizing, single instance. Limiter interface to swap. AI limits in the DB are authoritative. |
| R-10 | iOS E2E in CI requires macOS runners (cost) | Medium | Low | Run Maestro locally before releases. Android E2E in CI on Linux if feasible. |
| R-11 | App Store / Play review rejections (account deletion, privacy labels, guest accounts, minimum functionality) | Medium | Medium | In-app deletion, accurate labels, real content at submission, privacy policy URL |
| R-12 | Expo SDK and React Native upgrade churn during development | Medium | Low | Pin the SDK at project start. Upgrade deliberately between releases. |
| R-13 | Legal documents (privacy policy, terms) are not an engineering deliverable but block public release | High | High (blocks launch) | Owner obtains them before beta (TestFlight external testing also requires a privacy policy URL) |
| R-14 | Developing on Windows: `make`, file watching in Docker, and iOS builds require macOS (or EAS cloud builds) | High | Low | npm/uv scripts mirror the Makefile. EAS Build for iOS binaries. Expo Go or a dev client on a physical iPhone for testing. |
| R-15 | Pricing or model availability of the AI provider changes | Low | Low | Model and prices are config-driven. Shared cache bounds the cost. Kill switch. |

## 15.5 External dependencies

| Dependency | Needed for | Owner action |
|---|---|---|
| Apple Developer Program + Google Play Console accounts | Builds, TestFlight, store release | Owner |
| Expo / EAS account | Cloud builds, OTA updates | Owner |
| Anthropic API account and key (staging and production, separate keys) | AI explanations | Owner |
| Transactional email provider and sending domain (SPF/DKIM) | Password reset | Owner (D-2) |
| Hosting account (API + Postgres + cron) | Staging and production | Owner (D-7) |
| Domain name for the API and the reset fallback page | HTTPS, deep links | Owner |
| Psychology reviewer | Editorial review | Owner (D-13) |
| Illustrator / diagram creation | Optional lesson images | Owner |
| Privacy policy and terms | Store listings, beta | Owner (R-13) |
| Sentry account (if D-11 approved) | Error tracking | Owner |


## 15.6 Deviations recorded during implementation

| ID | Spec said | Implemented | Reason | Follow-up |
|---|---|---|---|---|
| DEV-1 | `users.email` as `citext` | `text` with a unique constraint and `CHECK (email = lower(email))`. The app trims and lowercases emails. | Same guarantee without depending on a Postgres extension. The embedded Postgres used for local tests lacks `citext`. | None |
| DEV-2 | Refresh reuse within the grace window returns the already-issued successor | Issues a new sibling token in the same family | Only token hashes are stored, so the successor can't be re-sent | None. Family revocation after the grace window is unchanged. |
| DEV-3 | Bundled top-10,000 common-password list | Interim curated list of common passwords of 10+ characters (`app/auth/common_passwords.txt`), plus a repeated-character check | A large list must come from a vetted source and wasn't downloaded | Owner to supply a vetted list (e.g. a filtered public breach-frequency list). Drop-in file replacement. |
| DEV-4 | `streak_states` row created with the user | **Resolved in the gamification slice:** the row is created on the first qualifying event with 1 freeze | — | None |
| DEV-5 | Interests stored in `user_topic_interests` | **Resolved in the content slice:** the table exists, and `PATCH /me/preferences` validates slugs against published topics and replaces the set | — | None |
| DEV-6 | Password reset, data export, global per-user/IP rate limits | Data export is **done** (`GET /me/export`). Password reset and global per-user/IP rate limits are still missing. | Reset needs the email provider (D-2) | Password reset with the email provider; global limits before the beta |
| DEV-7 | Content hash excludes only `status` and `position` | Also excludes `last_reviewed_on`, `reviewers`, `changelog`, `related`, `prerequisites` | Otherwise publishing a reviewed draft, or adding a related link, would need a version bump although the lesson text is unchanged | None |
| DEV-8 | Topic slugs unique within a subject | Validator requires topic slugs to be unique across all subjects | The API identifies topics by slug alone (interests, `?topic=` filter) | None |
| DEV-9 | `GET /lessons` cursor pagination in SQL | Published lessons are loaded, filtered by topic/progress in memory, then paginated with a keyset cursor over the curated order | The progress filter needs per-user state. The library is small (≤ 100s of lessons). | Move filtering into SQL if the library grows past ~500 lessons |
| DEV-10 | Lesson images served with hashed names and long cache headers | `/media/<slug>/<file>` served by the API from `content/media` with default static-file headers | No lesson has images yet | Add content hashing to file names and `Cache-Control: immutable` when images are introduced |
| DEV-11 | Lesson cards show per-user progress | **Resolved in the learning slice:** derived from progress milestones, review state and open attempts | — | None |
| DEV-12 | Options shuffled with seed `(attempt_id or session_item_id, question_id)` | `GET /lessons/{slug}` (no attempt yet) seeds with `(user_id, question_id)` | Stable order per user before an attempt exists | Attempt responses will use the attempt seed |
| DEV-13 | `POST /attempts/{id}/complete` returns `xp_awarded`, `xp`, `streak`, `achievements_unlocked`, and completion updates XP, streak, daily activity and achievements | **Resolved in the gamification slice:** completion now writes XP, streak, daily activity and achievements in the same transaction and returns all spec fields | — | None |
| DEV-14 | `POST /attempts/{id}/rating` and `POST /lessons/{slug}/feedback` | **Resolved:** `POST /attempts/{id}/rating` and `POST /lessons/{slug}/feedback` are implemented | — | None |
| DEV-15 | Completion's `next_lesson` falls back to the recommendation rules (07 §7.8) | **Resolved in the Discover slice:** completion and `/discover` share `app/learning/recommendations.py` (interests, prerequisites, related boost) | — | None |
| DEV-16 | Review item answers and session completion return `xp_awarded`, `streak`, `achievements_unlocked` and apply XP, streaks and achievements | **Resolved in the gamification slice:** review answers now award XP, record the streak day when the session completes, and return `xp_awarded`, `streak` and `achievements_unlocked` | — | None |
| DEV-17 | `review_sessions` has `completed_at` only | Also `ended_at`, set when a session ends early or expires | Keeps "completed" (all items answered, used by metric M2) separate from other closings | None |
| DEV-18 | Session estimate `ceil(due_count × 0.5)` minutes | `ceil(min(due_count, 20) × 0.5)` | A session holds at most 20 items | None |
| DEV-19 | `xp_transactions` references `lesson_id`, `attempt_id`, `review_session_id`. `user_achievements` stores `earned_at`. | Adds `xp_transactions.review_session_item_id` and `user_achievements.source_key` (`attempt:<id>` / `review_item:<id>`). The daily-goal row also carries the triggering attempt or item. | Replays must return the same `xp_awarded` and `achievements_unlocked` as the original request | None |
| DEV-20 | AC-DISC-2: `/discover` P95 ≤ 300 ms at seeded scale | Not measured yet. The endpoint runs about 15 small indexed queries. | Needs a benchmark harness with seeded data | Add a timing test or load script before the beta; batch the queries if the target is missed |
| DEV-21 | Optional `curiosity ai pregenerate` and `curiosity ai review` (08 §8.2, §8.6) | **Resolved:** `curiosity ai pregenerate`, `ai review` (interactive), `ai list` and `ai set-status` exist. Pre-generation records cost on `ai_explanations` only. | — | None |
| DEV-22 | `flag_count` increments only the first time a user flags | `flag_count` is recomputed as the number of users whose current rating is `incorrect` | Same "one flag per user" rule, and a user who changes their rating removes their flag | None |
| DEV-23 | Anthropic provider verified end to end | Request shape and response parsing are unit-tested against a mocked client (SDK 1.15.0). Not yet called against the live API with structured output plus `fallbacks: "default"`. | No API key in development | Run one real request per mode in staging before enabling `AI_PROVIDER=anthropic`. If the API rejects the combination, set `AI_REFUSAL_FALLBACK=false`. |
| DEV-24 | Cost of every provider call recorded | Cost uses the final response's `model` and `usage`. Tokens spent by a declined first model during a server-side fallback (`usage.iterations`) are not added. | Fallbacks should be rare. The provider invoice stays authoritative. | Sum `usage.iterations` if fallback volume turns out significant |
| DEV-25 | Content feedback on any lesson | Only published lessons accept reports. A version or question that doesn't belong to the lesson returns `422 INVALID_REFERENCE` (a new error code). | Retired lessons aren't shown in the app. Mismatched references would make reports unusable for editors. | None |
| DEV-26 | `product_events.user_id` is a cascading FK | Same FK, but nullable, so `account_deleted` can be stored without a user id and survive the cascade | Spec 12 §12.2 requires the anonymised deletion event | None |
| DEV-27 | Interest "Thinking clearly" maps to `foundations` and `judgment` | Each interest card maps to one topic (thinking → `judgment`, decisions → `decisions`, people → `social`) | With two topics, picking all three cards would exceed the API's limit of 3 interest topics. `foundations` comes first in curated order anyway. | None |
| DEV-28 | After onboarding the user lands on the first lesson's intro (FR-ONB-4) | **Resolved:** after onboarding the app opens today's lesson intro, and Discover, Learn and Recall are all built. Tab icons arrived with D-16. | — | None |
| DEV-29 | `make api-types` with openapi-typescript as a dev dependency | `npm run api-types` (backend `curiosity openapi`, then a pinned `npx openapi-typescript@7.13.0`) | openapi-typescript 7.13.0 (latest) requires TypeScript 5, and the app uses TypeScript 6 | Make it a dev dependency once a TypeScript 6-compatible release exists |
| DEV-30 | Typed routes (06 §6.3) | Expo Router's typed routes are off | Their generated types live in `.expo/` (not committed), so CI and local type-checks would disagree | Turn on once route types can be generated in CI |
| DEV-31 | Lesson player overflow menu with Sources and Report a problem (FR-LRN-5), "Explain differently" (J4), and offline caching of fetched lessons (FR-GLB-2) | Not in the player yet. Research examples show their citation inline. | Kept the slice to reading, answering and completing | Add with the mobile AI and offline slices |
| DEV-32 | Recall: mastery dots animate on change; "Concepts in review" is paginated (FR-REC-1) | Dots update without animation. The concepts list loads the first 100 concepts only. | Animation belongs to the motion pass. 100 covers the whole MVP library (27 lessons). | Add motion with the design pass; paginate when the library passes 100 lessons |
| DEV-33 | Discover header shows today's XP as a ring (02 §2.5, 10 §10.3 `XpRing`) | A pill with "15/20 XP today" and a thin progress bar | A ring needs an SVG dependency (react-native-svg) that nothing else needs yet | Add `XpRing` with the design pass if the ring is still wanted |
| DEV-34 | Terms of Use and Privacy Policy linked from Welcome and About (09 §9.7) | Welcome mentions them in text; About has no links yet | The documents don't exist yet (R-13, owner action) | Add the URLs once the documents are published |

## 15.7 Change log for this spec

| Version | Date | Change |
|---|---|---|
| 0.1 | 2026-10-18 | Initial draft for approval |
| 1.0 | 2026-10-18 | D-1 to D-15 approved as recommended. Spec is the baseline for implementation. |
| 1.1 | 2026-10-22 | D-16: playful path-based UI replaces the editorial direction (02 §2.1, 10 §10.1). |
| 1.2 | 2026-10-23 | D-17 subjects with their own roadmaps; D-18 estimate questions (03, 04, 05). |
