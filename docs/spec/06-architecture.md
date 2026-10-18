# 06 — Application Architecture and Project Structure

## 6.1 System overview

```
┌──────────────────────┐     HTTPS/JSON      ┌───────────────────────────────────────────┐      ┌──────────────┐
│ Expo app (iOS/Android)│ ─────────────────► │ FastAPI modular monolith (1 container)     │ ───► │ PostgreSQL 16│
│ TanStack Query cache  │ ◄───────────────── │ auth · content · learning · reviews ·     │      └──────────────┘
│ SecureStore (tokens)  │                    │ gamification · ai · privacy · analytics    │
└──────────────────────┘                    └───────────────┬───────────────────────────┘
                                                            │ HTTPS (server-side key only)
                                                            ▼
                                                   Anthropic Messages API
                                                   Transactional email provider
```

- **One deployable backend** (a modular monolith). Modules talk to each other through Python function calls on service interfaces. There are no events, queues, or workers.
- Scheduled maintenance tasks (guest purge, token cleanup) are **CLI commands** run by the hosting platform's cron feature (see [13](13-operations.md)). No worker infrastructure is involved.
- **Sync stack**: SQLAlchemy 2.0 sync sessions + psycopg 3. FastAPI runs `def` endpoints in its threadpool. The AI call (≤ 15 s) blocks one thread, which is acceptable at MVP scale (threadpool 40, see R-9). D-14 records the choice to stay sync rather than async.

## 6.2 Backend structure (`apps/api`)

```
apps/api/
├── pyproject.toml            # uv-managed; ruff, mypy (strict), pytest config
├── uv.lock
├── Dockerfile                # multi-stage, non-root user, uvicorn
├── alembic.ini
├── migrations/               # Alembic env + versions (hand-reviewed autogenerate)
├── app/
│   ├── main.py               # create_app(): routers, middleware, exception handlers
│   ├── config.py             # Settings (pydantic-settings), single source of env config
│   ├── core/
│   │   ├── db.py             # engine, SessionLocal, get_db dependency, transaction helper
│   │   ├── clock.py          # Clock protocol, SystemClock, local_today()
│   │   ├── errors.py         # AppError hierarchy → error envelope; handlers
│   │   ├── logging.py        # structlog JSON config, request_id contextvar
│   │   ├── middleware.py     # request id, access log, app-version gate
│   │   ├── ratelimit.py      # RateLimiter protocol + in-memory fixed window impl
│   │   ├── security.py       # password hashing (argon2), JWT encode/decode, token gen
│   │   ├── ids.py            # uuid7()
│   │   └── pagination.py
│   ├── auth/
│   │   ├── router.py         # /auth/*, /me/password
│   │   ├── schemas.py        # Pydantic request/response models
│   │   ├── service.py        # register, login, upgrade, refresh rotation, reset
│   │   ├── models.py         # User, RefreshToken, PasswordResetToken
│   │   ├── deps.py           # get_current_user, require_full_account
│   │   └── email.py          # EmailSender protocol: ConsoleEmailSender, ProviderEmailSender
│   ├── users/                # /me, preferences, export, deletion (privacy)
│   │   ├── router.py · schemas.py · service.py · models.py
│   ├── content/
│   │   ├── schema.py         # Pydantic models for YAML lesson files (authoring schema)
│   │   ├── loader.py         # read + validate content dir
│   │   ├── importer.py       # idempotent DB import (transactional)
│   │   ├── models.py         # Subject, Topic, Lesson, LessonVersion, Question, AnswerOption, Source, …
│   │   ├── repository.py     # published lesson queries
│   │   ├── router.py         # /subjects, /lessons, /lessons/{slug}
│   │   └── schemas.py        # API output models (no correctness fields!)
│   ├── learning/
│   │   ├── router.py         # attempts, answers, complete, rating, feedback, /discover, /progress
│   │   ├── service.py        # attempt lifecycle, grading
│   │   ├── grading.py        # pure: grade(question, selected) → is_correct
│   │   ├── progress.py       # pure: status/mastery derivation
│   │   ├── recommendations.py
│   │   ├── models.py         # LessonAttempt, LessonAttemptAnswer, UserLessonProgress, LessonRating, ContentFeedback
│   │   └── schemas.py
│   ├── reviews/
│   │   ├── scheduler.py      # pure SM-2 implementation (Scheduler protocol)
│   │   ├── selection.py      # pure: question selection
│   │   ├── service.py        # sessions, answering (transactions, locks)
│   │   ├── repository.py     # due_review_states(), etc.
│   │   ├── router.py · schemas.py · models.py
│   ├── gamification/
│   │   ├── xp.py             # award(...) with idempotency keys
│   │   ├── streaks.py        # pure transition + display functions
│   │   ├── achievements.py   # registry + evaluate(...)
│   │   ├── daily_activity.py
│   │   ├── service.py        # apply_lesson_completion(), apply_review_answer(), …
│   │   ├── router.py         # /achievements
│   │   └── models.py
│   ├── ai/
│   │   ├── provider.py       # ExplanationProvider protocol; AnthropicProvider; FakeProvider
│   │   ├── prompts.py        # versioned prompt templates (explain-v1)
│   │   ├── guard.py          # output validation
│   │   ├── limits.py         # per-user + global budget checks (DB-backed)
│   │   ├── pricing.py        # model → price table (config-overridable)
│   │   ├── service.py        # cache lookup → limits → generate → store
│   │   ├── router.py · schemas.py · models.py
│   ├── analytics/
│   │   ├── events.py         # server-side emit(name, user, props) within txn
│   │   ├── router.py         # POST /events (whitelist)
│   │   └── models.py
│   ├── health/router.py
│   └── cli.py                # `curiosity` Typer CLI: content validate|import|new|feedback, ai review, maintenance purge-guests|cleanup-tokens, users mark-internal
└── tests/
    ├── conftest.py           # Postgres test DB, transactional fixtures, FixedClock, FakeProvider, factories
    ├── unit/                 # scheduler, streaks, xp keys, grading, progress, recommendations, content schema, guard
    ├── integration/          # API tests per router against real Postgres
    └── fixtures/content/     # minimal valid + invalid lesson YAMLs
```

**Layering rules**
- `router` → validates the request and calls `service`. It never touches the ORM directly. It maps domain results to schemas.
- `service` → owns the transaction (`with db.begin():`) and orchestrates repositories, pure domain modules, and other modules' services.
- Pure modules (`scheduler`, `streaks`, `grading`, `progress`, `selection`, `recommendations`, `guard`) have **no I/O** and receive `today`/`now` explicitly.
- `repository` modules exist only where queries are non-trivial or reused (content, reviews). Elsewhere, services use the session directly. No generic repository abstraction.
- Cross-module calls go through the other module's `service.py` public functions. Importing another module's `models.py` is allowed for relationships only.
- Gamification is applied **inside** the learning and review transactions by calling `gamification.service` functions. It is not async.
- Errors are raised as `AppError(code, status, message, details)` subclasses and turned into the error envelope by one handler.

**Configuration** (`config.py`, all environment variables, see [13 §13.3](13-operations.md#133-configuration)). Settings are validated at startup, and the app refuses to start on missing required secrets in `production`.

**Logging**: structlog JSON to stdout. Every log line carries `request_id`, `user_id` (UUID only), `route`, `status`, `duration_ms`. Emails, tokens, passwords, answer text, and AI prompt bodies are never logged.

## 6.3 Mobile structure (`apps/mobile`)

```
apps/mobile/
├── app.config.ts              # Expo config; env-driven API URL, bundle ids
├── eas.json                   # build profiles: development, preview, production
├── package.json               # pinned Expo SDK (latest stable at project start)
├── tsconfig.json              # strict
├── app/                       # Expo Router routes (screens are thin)
│   ├── _layout.tsx            # providers: QueryClient, Theme, Auth, SafeArea, ErrorBoundary
│   ├── (auth)/welcome.tsx · login.tsx · forgot-password.tsx · reset-password.tsx
│   ├── (onboarding)/interests.tsx · goal.tsx
│   ├── (tabs)/_layout.tsx     # Discover | Learn | Recall
│   ├── (tabs)/index.tsx       # Discover
│   ├── (tabs)/learn.tsx
│   ├── (tabs)/recall.tsx
│   ├── lesson/[slug]/index.tsx        # intro
│   ├── lesson/[slug]/play.tsx         # player (modal presentation)
│   ├── review/[sessionId].tsx         # review session (modal)
│   ├── profile/index.tsx · achievements.tsx
│   ├── settings/index.tsx · account.tsx · learning.tsx · appearance.tsx · privacy.tsx · about.tsx
│   └── report.tsx                     # modal
├── src/
│   ├── api/
│   │   ├── schema.d.ts        # GENERATED from OpenAPI (openapi-typescript); do not edit
│   │   ├── client.ts          # fetch wrapper: base URL, auth header, refresh-once, error mapping
│   │   ├── errors.ts          # ApiError, code → user message map
│   │   └── endpoints/         # typed functions per resource (auth.ts, lessons.ts, reviews.ts, …)
│   ├── features/              # feature hooks + feature-specific components
│   │   ├── auth/              # AuthProvider (SecureStore), useSession
│   │   ├── discover/          # useDiscover (TanStack Query), PrimaryActionCard
│   │   ├── lessons/           # useLessonAttempt, usePlayerState (step machine), StepRenderer, steps/*
│   │   ├── reviews/           # useReviewSession, ReviewItem, SessionSummary
│   │   ├── ai/                # useExplanation, ExplanationSheet
│   │   ├── progress/          # useProgress, useAchievements
│   │   └── analytics/         # track() batching queue → POST /events
│   ├── ui/                    # design-system components (no data fetching)
│   │   ├── tokens.ts          # colors (light/dark), type scale, spacing, radii, motion
│   │   ├── theme.tsx          # ThemeProvider, useTheme (system/light/dark)
│   │   ├── Text.tsx · Button.tsx · Card.tsx · OptionCard.tsx · FeedbackPanel.tsx · ProgressBar.tsx
│   │   ├── MasteryDots.tsx · StreakBadge.tsx · XpRing.tsx · Banner.tsx · EmptyState.tsx · Skeleton.tsx
│   │   ├── Sheet.tsx · Markdown.tsx (restricted subset) · AiBadge.tsx
│   ├── lib/                   # storage.ts (SecureStore/AsyncStorage wrappers), haptics.ts, netinfo.ts, dates.ts
│   └── i18n/en.ts             # all user-facing strings (English only in MVP, but centralised)
├── assets/                    # fonts, icons, app icon, splash
├── e2e/                       # Maestro flows (*.yaml)
└── __tests__/                 # Jest + React Native Testing Library
```

**Responsibilities**
- **Routes** (`app/`) compose feature components and handle navigation. They contain no business logic.
- **State management**:
  - *Server state*: **TanStack Query**. Query keys per resource. Mutations invalidate `discover`, `progress`, `reviews/summary`, and `lessons` as appropriate. Discover/library/lesson content is persisted to AsyncStorage (query persister) for offline viewing.
  - *Session state*: `AuthProvider` (React context) backed by `expo-secure-store` for tokens.
  - *Local UI state*: component state and small reducers (lesson player step machine). **No Redux or Zustand** unless a real need appears.
  - *Preferences on the device*: theme choice, last step index per attempt (AsyncStorage).
- **API access**: only through `src/api`. The client adds headers, refreshes the token once on `401 UNAUTHENTICATED` (with a single in-flight refresh promise), and throws a typed `ApiError` with `code`.
- **Correctness logic**: none on the client. The client never sees correct answers until the server returns `AnswerResult`.
- **Accessibility**: every `ui` component accepts and forwards accessibility props. Text uses `Text` from `ui`, which applies the type scale and font scaling limits.
- **Tooling**: TypeScript strict, ESLint (expo config + react-hooks), Prettier, Jest, RNTL, Maestro. Fonts via `expo-font` (bundled). Animations via `react-native-reanimated`, respecting the OS "reduce motion" setting.

## 6.4 Contract between client and server

1. The backend defines Pydantic response models. FastAPI produces OpenAPI.
2. `make api-types` (in the repo root) exports `openapi.json` from the app without running a server, then runs `openapi-typescript` → `apps/mobile/src/api/schema.d.ts`.
3. CI regenerates the types and fails if the result differs from the committed file (contract drift check).
4. The API is versioned under `/v1`. Breaking changes require `/v2` or a coordinated `MIN_APP_VERSION` bump (see [13](13-operations.md)).

## 6.5 Working agreements for AI-assisted development

- Each change implements a slice end-to-end: migration → model → service (with unit tests) → router (with integration tests) → client hook → screen.
- Generated code is reviewed against this spec. Any deviation is recorded in [15-decisions-and-risks.md](15-decisions-and-risks.md) in the same commit.
- No new dependency or infrastructure without a note in the commit message stating the requirement it satisfies.
- `CLAUDE.md` (to be written at implementation start) points to this spec, lists the commands (`make test`, `make lint`, `make api-types`, `curiosity content validate`), and states the git rules (local commits only, never push).
