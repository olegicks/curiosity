# Curiosity — working notes for AI assistants

Curiosity is a mobile learning app (psychology and cognitive biases): understand an idea, test your understanding, and remember what you learn.

## Source of truth

**`docs/spec/` is the primary reference.** Read [docs/spec/README.md](docs/spec/README.md) first, then only the files a task needs. The spec is approved (v1.0). When implementation must deviate, record the deviation in `docs/spec/15-decisions-and-risks.md` in the same commit. Never diverge silently.

Key files by task:
- Endpoints and wire formats → `05-api.md`
- Tables, constraints, transactions → `04-data-model.md`
- Scheduler, progress, XP, streaks, achievements → `07-learning-engine.md`
- Project layout and layering rules → `06-architecture.md`
- Tests required and Definition of Done → `11-testing-acceptance.md`

## Repository layout

```
apps/api/      FastAPI modular monolith (Python 3.13, uv, SQLAlchemy 2 sync, Alembic, Postgres 16)
apps/mobile/   Expo SDK 58 + React Native + TypeScript 6 (Expo Router, TanStack Query)
content/       Lesson YAML files: the canonical content
demo-content/  Demo lessons for local device testing only (not reviewed; never import into production)
docs/spec/     Specification
```

## Backend commands (run from `apps/api/`)

```bash
uv sync                          # install deps into .venv
uv run pytest                    # tests (DB tests need TEST_DATABASE_URL, otherwise skipped)
uv run ruff check . && uv run ruff format --check .
uv run mypy app
uv run alembic upgrade head      # needs DATABASE_URL
uv run uvicorn --factory app.main:create_app --reload
uv run curiosity --help             # content import/validate, AI review, OpenAPI export
```

With Docker available, `docker compose up` from the repo root starts Postgres and the API.

## Mobile commands (run from `apps/mobile/`)

```bash
npm install
npx expo start                   # dev server; set EXPO_PUBLIC_API_URL in .env.local
npm run lint && npm run typecheck && npm test
npm run api-types                # regenerate src/api/schema.d.ts from the API (needs uv)
```

- API types are generated, never hand-edited. CI fails if `src/api/schema.d.ts` drifts from the API.
- All API access goes through `src/api` (client with one shared token refresh). Screens never call `fetch`.
- No correctness logic in the client: the server grades answers and computes progress and XP.
- UI uses the tokens in `src/ui/tokens.ts`; copy lives in `src/i18n/en.ts`.

## Architecture rules (summary of 06-architecture.md)

- Layers: `router` (HTTP + schemas) → `service` (owns transactions) → pure domain modules (no I/O; take `today`/`now` explicitly) and repositories where useful.
- The backend is authoritative for correctness, progress, scheduling and XP. Never put this logic in the client.
- Every owner-scoped query filters by `user_id`. A foreign resource returns **404**, never 403.
- Errors: raise `AppError` subclasses (`app/core/errors.py`). They render as `{"error": {code, message, details, request_id}}`.
- Time: always use the injected `Clock` (`app/core/clock.py`), never `datetime.now()` in domain code.
- IDs: `app.core.ids.uuid7()`.
- Never log emails, tokens, passwords, answer text, or AI prompts. Log user UUIDs only.
- Don't add dependencies or infrastructure (Redis, queues, workers) without a requirement in the spec. Mention the requirement in the commit message.

## Testing rules

- Pure modules get unit tests. Endpoints get integration tests against **real PostgreSQL**, never SQLite.
- Tests that touch the DB use the `db_session` / `client` fixtures and are skipped automatically when `TEST_DATABASE_URL` is unset.
- Use `FixedClock` for anything time-dependent. No sleeps.

## Git rules

- Make small, meaningful commits after each logical unit. Use Conventional Commits (`feat:`, `fix:`, `docs:`, `test:`, `chore:`, `refactor:`).
- Review the diff before committing. Never commit secrets, `.env` files, credentials, or generated artifacts (`.venv`, caches, build output).
- **Never push** and never create remote branches or pull requests. The owner reviews and pushes.
- Don't rewrite or delete existing commits unless explicitly authorized.

## Environment notes

- The primary developer machine is Windows. Prefer `uv run …` commands over `make`.
- Docker and a local Postgres may not be installed. When they are missing, DB-backed tests are skipped locally and run in CI.
