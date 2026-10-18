# 13 — Deployment, Environment Configuration and Operations

## 13.1 Environments

| Env | Purpose | API | Database | AI | Email |
|---|---|---|---|---|---|
| `local` | Development | `docker compose` (API with reload) | Postgres container | `FakeProvider` by default. Real provider optional with a personal key. | Console sender |
| `test` | CI and pytest | in-process | Postgres service container | `FakeProvider` only | Captured in memory |
| `staging` | Pre-release verification, beta builds | 1 container | Managed Postgres (small) | Real provider, low budget (USD 1/day) | Real provider (sandbox domain) |
| `production` | Live | 1 container (vertical scaling first) | Managed Postgres with automated backups + PITR | Real provider | Real provider |

## 13.2 Local development

`docker-compose.yml` (to be written):
- `db`: `postgres:16`, volume, healthcheck, port 5432 exposed locally only.
- `api`: built from `apps/api/Dockerfile` (dev target), mounts source, runs `alembic upgrade head && curiosity content import && uvicorn app.main:app --reload`, depends on `db` being healthy, port 8000.
- The mobile app runs on the host (`npx expo start`), pointing `EXPO_PUBLIC_API_URL` at the host's LAN IP.

Task runner: a root `Makefile` for macOS/Linux/CI, mirrored by `npm run`/`uv run` scripts so Windows developers don't need `make`. Commands: `test`, `lint`, `typecheck`, `api-types`, `content-validate`, `seed-demo` (creates a demo user with due reviews for E2E).

## 13.3 Configuration

Backend variables (all in `.env.example` with dummy values):

| Variable | Required | Default | Notes |
|---|---|---|---|
| `APP_ENV` | yes | `local` | `local`/`test`/`staging`/`production` |
| `DATABASE_URL` | yes | — | `postgresql+psycopg://…` |
| `DB_POOL_SIZE` | no | 10 | |
| `JWT_SECRET` | yes | — | ≥ 32 bytes. In production the app refuses to start if it is missing or weak. |
| `ACCESS_TOKEN_TTL_SECONDS` | no | 900 | |
| `REFRESH_TOKEN_TTL_DAYS` | no | 30 | |
| `MIN_APP_VERSION` | no | `1.0.0` | Below this → 426 |
| `CORS_ORIGINS` | no | empty | Not used by mobile |
| `FORWARDED_ALLOW_IPS` | prod | — | Trusted proxy IPs for the client IP |
| `EXPOSE_OPENAPI` | no | true (non-prod), false (prod) | |
| `LOG_LEVEL` | no | `INFO` | |
| `SENTRY_DSN` | no | — | D-11 |
| `EMAIL_PROVIDER` | yes (staging/prod) | `console` | |
| `EMAIL_API_KEY` | staging/prod | — | |
| `EMAIL_FROM` | staging/prod | — | |
| `PASSWORD_RESET_URL_BASE` | yes | `curiosity://reset` | |
| `AI_EXPLANATIONS_ENABLED` | no | true | Kill switch |
| `AI_PROVIDER` | no | `fake` (local/test), `anthropic` (staging/prod) | |
| `ANTHROPIC_API_KEY` | when the provider is anthropic | — | |
| `AI_MODEL` | no | `claude-opus-5-5` | D-6 |
| `AI_EFFORT` | no | `low` | |
| `AI_TIMEOUT_SECONDS` | no | 15 | |
| `AI_MAX_VARIANTS` | no | 3 | |
| `AI_USER_DAILY_LIMIT` / `AI_USER_BURST_LIMIT` | no | 20 / 5 | |
| `AI_DAILY_BUDGET_MICROS` | no | 5000000 | |
| `AI_PRICE_INPUT_PER_MTOK_MICROS` / `AI_PRICE_OUTPUT_PER_MTOK_MICROS` | no | from `pricing.py` | |
| `CONTENT_DIR` | no | `/app/content` | Content is baked into the image |
| `CONTENT_ALLOW_DRAFT_OVERWRITE` | no | false | true only in local |
| `GUEST_RETENTION_DAYS` | no | 30 | |

Mobile (`EXPO_PUBLIC_*`, non-secret): `EXPO_PUBLIC_API_URL`, `EXPO_PUBLIC_ENV`, `EXPO_PUBLIC_SENTRY_DSN` (optional).

## 13.4 CI (GitHub Actions, `.github/workflows/ci.yml`)

Runs on pull requests and on pushes to `main`. The repository owner pushes; the CI configuration only defines the jobs.

| Job | Steps |
|---|---|
| `api` | set up uv → install → `ruff check` → `ruff format --check` → `mypy app` → start a Postgres service → `alembic upgrade head` → `alembic check` → `pytest --cov` → `pip-audit` |
| `content` | `curiosity content validate content/` → import into an empty Postgres |
| `mobile` | set up Node (LTS) → `npm ci` → `eslint` → `tsc --noEmit` → `jest` → `npm audit --omit=dev --audit-level=critical` |
| `contract` | export OpenAPI → `openapi-typescript` → `git diff --exit-code apps/mobile/src/api/schema.d.ts` |
| `docker` | build the production image (no push) |

E2E (Maestro) is a separate manually triggered workflow, or runs locally before releases (R-10).

## 13.5 Deployment procedure (backend)

Target: a container PaaS with managed Postgres and scheduled jobs (D-7; candidates are Fly.io, Render, Railway, or a cloud provider's equivalent). The procedure is the same regardless of provider:

1. **Build**: production Docker image (multi-stage, slim Python, non-root, `content/` copied in) tagged with the git SHA.
2. **Release step** (runs once per deploy, before traffic shifts):
   1. `alembic upgrade head`
   2. `curiosity content import`
   If either fails, the deploy aborts and the previous version keeps serving.
3. **Start**: `uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2 --proxy-headers`.
   *Note:* with 2 workers the in-process rate limiter is per worker, which makes limits up to 2× looser. This is accepted for the MVP (R-9). Use 1 worker if strict limits matter more than throughput.
4. **Health**: the platform checks `/health/ready` before routing traffic and rolls back if it fails.
5. **Migrations must be backward compatible** with the previous app version during rollout (expand → migrate → contract across two releases for destructive changes).
6. **Scheduled jobs** (platform cron, same image):
   - daily 03:00 UTC: `curiosity maintenance purge-guests`
   - daily 03:30 UTC: `curiosity maintenance cleanup-tokens` (expired refresh and reset tokens)
7. **Rollback**: redeploy the previous image tag. Migrations are only rolled back if they are verified safe. Prefer a forward fix.

## 13.6 Mobile release procedure

1. Versioning: semantic `MAJOR.MINOR.PATCH`. `buildNumber`/`versionCode` are incremented by EAS automatically.
2. `eas build --profile preview` → internal distribution (TestFlight internal / Play internal testing) against staging.
3. Manual QA checklist plus Maestro flows.
4. `eas build --profile production` → `eas submit` (performed by the repository owner with their store credentials).
5. **API compatibility:** the backend stays compatible with every app version ≥ `MIN_APP_VERSION`. Raise `MIN_APP_VERSION` only after the new version is available in both stores.
6. **OTA updates** (EAS Update) are allowed for JS-only fixes in the same runtime version. They are never used to change API contracts.

## 13.7 Observability and operations

- **Logs**: JSON to stdout, collected by the platform. 30-day retention. Fields as described in [06 §6.2](06-architecture.md#62-backend-structure-appsapi).
- **Errors**: Sentry for backend and mobile if approved (D-11). Otherwise platform logs plus Expo crash reports.
- **Uptime**: external check on `/health/ready` every 1 minute, alerting the owner by email.
- **Key operational checks** (weekly, via `curiosity analytics report --ops`): 5xx rate, P95 latency per route, AI spend vs budget, AI failure rate, open content feedback count, and the guest purge count.
- **Backups**: managed daily backups plus PITR (≥ 7 days). A restore drill into staging is done once before public launch.
- **Incident basics**: the AI kill switch (`AI_EXPLANATIONS_ENABLED=false`) without redeploy if the platform supports runtime environment changes, otherwise a redeploy. Maintenance mode returns 503 `SERVICE_UNAVAILABLE`.
- **Content hotfix**: retire or fix a lesson → PR → deploy (the import runs automatically). Target: S1 fixes live within 2 working days.
