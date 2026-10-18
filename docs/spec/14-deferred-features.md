# 14 — Deferred Features and Conditions for Adding Them

Each feature below is out of the MVP on purpose. "Trigger" lists the evidence that would justify building it. "Foundation already in place" lists what the MVP design already provides, so the later addition needs no redesign.

| Feature | Why deferred | Trigger to reconsider | Foundation already in place |
|---|---|---|---|
| **Review reminders (push or local notifications)** | Intrusive. Notification permissions and opt-in UX need care. The habit is unproven. | M1 < 20% while M4 ≥ 70% (people learn but don't return), *and* interview evidence that reminders are wanted | Due dates are computed server-side. Timezone is stored. |
| **Free-text answers with AI grading** | Grading reliability, cost, and the appeal and dispute process | Objective questions hit a ceiling (M8 shows recognition without transfer). A labeled evaluation set with ≥ 90% agreement with human graders. | Questions have a `type` field. Answers are stored per question. |
| **Conversational AI tutor** | Hard to keep grounded and safe, expensive, and competes with the core loop | ≥ 30% of AI users request multiple variants per lesson, with qualitative demand for follow-up questions | AI provider abstraction, prompts, guard, and usage tracking |
| **Knowledge-graph visualisation** | Little learning value at 27 lessons | ≥ 100 lessons, or users asking how concepts relate | `lesson_relations` (related, prerequisite) |
| **ML / adaptive recommendations** | Not enough data. Deterministic rules can be explained. | ≥ 5k MAU and enough review events to train and evaluate | All interactions are recorded in domain tables |
| **Smarter scheduler (FSRS, confidence grades)** | SM-2 variant is simpler and documented | M4 data shows systematic over- or under-scheduling. ≥ 50k review events. | `Scheduler` protocol, `scheduler_version` on states and events, before/after snapshots |
| **Additional subjects** (economics, statistics, …) | The psychology experience is not validated yet | M1 and M4 decision rule says "continue" (see [12 §12.4](12-analytics-validation.md#124-validation-plan)) | `subjects`/`topics` tables, content schema keyed by subject |
| **Social: feeds, sharing, friends, messaging** | Moderation burden. Not part of the value proposition. | Explicit, repeated user demand plus a moderation plan | — |
| **Leaderboards / competition** | Conflicts with the low-pressure principle | Probably never as a default. Maybe opt-in study groups. | XP ledger |
| **User-created lessons / community publishing** | Editorial quality is the core differentiator | A mature editorial process and moderation tooling | Content schema and validator could be reused |
| **Subscriptions / payments** | Validate value first | Retention and learning targets met. A pricing study. | Account system, server-side feature flags (`AI_*` limits per tier possible) |
| **Complex achievements / badges** | Badge clutter undermines the editorial feel | Evidence that milestones motivate (achievement unlock vs retention) | Code-defined achievement registry |
| **Analytics dashboards** | SQL reports are enough for a small team | More than one regular consumer of metrics | Metric SQL in the repo. Could connect Metabase to a read replica. |
| **Social login (Apple/Google)** | Adds vendor setup. If any third-party login is offered on iOS, Sign in with Apple is required too. | Upgrade-prompt conversion < 15%, or users mention password friction | `users` table can add `auth_identities` without changes |
| **Email verification** | Friction. Password reset is the only email use. | Abuse, or a need to email users (newsletters, notices) | `users.email`, email sender abstraction |
| **Web app / tablet layouts** | Focus on phones first | Demand from desktop learners or classrooms | REST API, CORS config option, responsive tokens |
| **Offline lesson completion and answer queueing** | The backend is authoritative, and conflict handling is complex | Offline usage share is significant (from `app_opened` without connectivity) | Natural idempotency of answer endpoints would allow safe replay |
| **Redis / distributed rate limiting** | Single instance | More than one API instance is needed | `RateLimiter` protocol |
| **Background workers / queues** | Nothing in the MVP needs async processing | AI pre-generation at scale, email volume, or heavy analytics jobs | Services are pure. CLI commands could move to a worker unchanged. |
| **Microservices / Kubernetes** | No demonstrated need | Team or scaling constraints that a monolith can't meet | Module boundaries inside the monolith |
| **Admin web UI (content, feedback, AI review)** | Git and the CLI are enough for one editor | More than 2 non-technical editors | CLI commands define the operations |
| **Localization** | English first | Validated market in another language | Strings centralised in `src/i18n`. Content schema could add a `locale`. |
| **"Science that didn't hold up" topic** | Needs careful editorial treatment | After the core library is stable | Evidence status fields |
