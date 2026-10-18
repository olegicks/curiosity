# 09 — Authentication, Privacy and Security

## 9.1 Authentication model

- **Guest-first** (D-1). `POST /auth/guest` creates a real server-side user with no credentials. The guest can later upgrade to email + password and keep the same `user_id`.
- **Credentials**: email + password only (D-2). Social login is deferred.
- **Access token**: JWT, HS256, signed with `JWT_SECRET` (≥ 32 random bytes), lifetime **15 minutes**. Claims: `sub` (user ID), `ver` (token_version), `guest` (bool), `iat`, `exp`, `iss`=`curiosity-api`, `aud`=`curiosity-app`. Each request verifies the signature, `exp`, `iss`, `aud`, and that `ver` matches `users.token_version`. That last check needs one indexed PK lookup, which the request already makes when it loads the user.
- **Refresh token**: 256-bit random, base64url, lifetime **30 days**, single use with rotation, and stored only as a SHA-256 hash. Reusing a rotated token (outside the 10-second grace window) revokes the whole family.
- **Mobile storage**: tokens live in `expo-secure-store` (Keychain / Keystore), never in AsyncStorage. They are cleared on logout, deletion, or refresh failure.
- **Passwords**: argon2id via `argon2-cffi` (library defaults or stronger; parameters configurable). Length 10–128. Rejected if the password appears in a bundled list of the 10,000 most common passwords or equals the email. No composition rules. The login path verifies against a dummy hash when the email is unknown, to equalise timing.
- **Password reset**: a single-use 256-bit token, hashed in the DB, expiring in 30 minutes, delivered by a transactional email provider (D-2). On reset, all refresh tokens are revoked and `token_version` is incremented.
- **Email verification**: not required in the MVP. The trade-off is that a typo'd email makes password reset impossible. This is mitigated by a confirmation field at upgrade (R-8).

## 9.2 Authorization and data isolation

- Every protected route depends on `get_current_user`. Routes that need a full account use `require_full_account`.
- **Ownership is enforced in queries**, not only in checks afterwards: service and repository functions take `user_id` and filter by it. A foreign resource behaves exactly like a missing one (`404`).
- Content endpoints only return `published` lessons, and only with `QuestionOut`/`OptionOut` schemas, which **structurally cannot carry** `is_correct`/`feedback`. Correctness is returned only in `AnswerResult` after the answer has been persisted.
- Integration tests include an **authorization matrix**: for every owner-scoped endpoint, user B requesting user A's resource receives 404, and A's data is unchanged (see [11](11-testing-acceptance.md)).
- There are no admin HTTP endpoints. Privileged operations (content import, AI review, marking internal users, purges) are CLI-only and run with database credentials in the deployment environment.

## 9.3 Input validation and safe data access

- Pydantic models on every request (`extra="forbid"`, explicit lengths, enums, UUID types).
- SQLAlchemy Core and ORM with bound parameters only. No string-built SQL. The `text()` construct is allowed only with bound parameters, and code review checks for it.
- JSONB inputs (`product_events.properties`) are filtered against a key whitelist and limited to 2 KB.
- Request body size limit: 64 KB (enforced by middleware and the reverse proxy).
- Markdown from content is rendered with a restricted renderer, never as HTML. AI output passes the guard and is rendered as plain text plus bold and lists.

## 9.4 Rate limiting

| Scope | Limit | Store |
|---|---|---|
| `POST /auth/login` | 5/min and 20/h per (IP, email). 50/h per IP | In-process fixed window (`core/ratelimit.py`) |
| `POST /auth/guest` | 10/h per IP | In-process |
| `POST /auth/register`, `/auth/upgrade` | 5/h per IP | In-process |
| Password reset request | 3/h per email, 10/h per IP | In-process |
| `/me/password` | 5/h per user | In-process |
| AI explanations | 20/24 h + 5/min per user, plus a global budget | **PostgreSQL** (`ai_requests`). Authoritative because it is tied to cost. |
| Content feedback | 10/day per user | PostgreSQL count |
| `/events` | 60/h per user | In-process |
| `/me/export` | 3/day per user | In-process |
| Global | 120 req/min per user, 300 req/min per IP | In-process |

The in-process limiter assumes **a single API instance** (MVP deployment). The `RateLimiter` protocol lets a Postgres- or Redis-backed implementation replace it if horizontal scaling becomes necessary (see [14](14-deferred-features.md)). The client IP comes from the platform's trusted proxy header only (`FORWARDED_ALLOW_IPS` configured).

## 9.5 Secrets and configuration

- All secrets come from environment variables injected by the hosting platform's secret store: `DATABASE_URL`, `JWT_SECRET`, `ANTHROPIC_API_KEY`, `EMAIL_API_KEY`, `SENTRY_DSN`.
- `.env` files are for local development only and are git-ignored (already in `.gitignore`). `.env.example` lists every variable with dummy values.
- The mobile app holds **no secrets**. Its only build-time configuration is the API base URL and environment name.
- The Docker image runs as a non-root user and contains no secrets. CI uses GitHub Actions secrets only for the steps that need them. Tests use `FakeProvider` and never real provider keys.
- `JWT_SECRET` rotation: changing it invalidates all access tokens. Refresh tokens are unaffected, because they are opaque and DB-backed, so clients transparently get new access tokens.

## 9.6 Account deletion

**Who:** any authenticated user (guest or full) via Settings → Privacy → Delete account (`DELETE /v1/me`). Apple requires account deletion inside the app, and this satisfies it.

**What happens (single transaction):**

| Data | Action |
|---|---|
| `users` row | Deleted |
| preferences, interests, refresh/reset tokens, attempts + answers, progress, review states/sessions/items/events, XP, streak, daily activity, achievements, lesson ratings, AI explanation feedback, product events | Deleted via `ON DELETE CASCADE` |
| `ai_requests` | `user_id` set to NULL (no content, cost accounting only) |
| `content_feedback` | `user_id` set to NULL. The message text is kept for editorial correction (disclosed in the privacy policy, D-15) |
| Shared AI explanations | Unaffected (contain no user data) |
| Backups | The data disappears when backups expire (managed Postgres PITR window ≤ 14 days, disclosed) |
| Logs | Contain only user UUIDs. Log retention 30 days |

After deletion, all tokens fail (the user row no longer exists). The client wipes SecureStore, AsyncStorage, and the query cache, then returns to Welcome.

**Guest purge:** guests with no activity for **30 days** (`last_seen_at`) are deleted by `curiosity maintenance purge-guests`, run daily by platform cron, using the same cascade (D-15).

**Data export:** `GET /me/export` (JSON) covers access and portability requests.

## 9.7 Data minimisation

| Collected | Why |
|---|---|
| Email (full accounts only) | Login, password reset |
| Password hash | Authentication |
| Display name (optional) | Greeting |
| Timezone | Streaks, due dates |
| Learning activity | Core functionality, learning metrics |
| App version, platform | Compatibility, debugging |
| Coarse product events | Product validation (no third-party analytics) |

Not collected: real name, birth date, location, contacts, device identifiers or advertising IDs, IP addresses in the DB (IPs appear transiently in rate limiting and in platform access logs with limited retention). There are no third-party ad or analytics SDKs. If adopted, Sentry is configured with `send_default_pii=False` and request bodies scrubbed (D-11).

**Legal documents required before public release** (dependency, not built by engineering): Privacy Policy and Terms of Use, reachable from Welcome and About. App Store privacy labels and the Play Data safety form must match §9.7.

## 9.8 Reliability controls

- **Repeated requests**: natural idempotency per endpoint ([05](05-api.md)), unique constraints, and `ON CONFLICT` handling.
- **Concurrency**: row locks (`FOR UPDATE`) on attempts, review states, and streak states. Fixed lock order ([04 §4.9](04-data-model.md#49-transaction-and-consistency-rules)).
- **Transactions**: each state-changing request is one DB transaction. Any exception rolls back everything, so there is no partial XP or progress.
- **AI isolation**: a separate endpoint with timeouts and no shared transaction with learning writes.
- **Safe errors**: a global exception handler logs the stack trace with `request_id` and returns the generic envelope.
- **Transport**: HTTPS only (platform TLS). HSTS on the API domain. CORS disabled (no browser clients). If a web client is added later, CORS will be enabled for named origins only.
- **Dependencies**: Dependabot (or equivalent) weekly. `pip-audit` and `npm audit --omit=dev` in CI (non-blocking warnings for moderate, blocking for critical).
