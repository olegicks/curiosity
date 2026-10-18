# Curiosity — MVP Specification

> Status: **Approved baseline** · Spec version 1.0 · 2026-10-18
> All decisions in [15-decisions-and-risks.md](15-decisions-and-risks.md) are approved as recommended. Record any deviation found during implementation in that file.

Curiosity is a personal learning app: **understand an idea, test your understanding, and remember what you learn.** The MVP covers one subject area (psychology and cognitive biases). It is built as a React Native (Expo) client and a FastAPI modular monolith on PostgreSQL.

This folder is the main reference for building the MVP. Each file covers one area so that a developer or AI coding assistant can load only what a task needs. When two files disagree, the more specific file wins: the API spec wins on wire formats and the data model wins on storage. Record the conflict as an issue in [15-decisions-and-risks.md](15-decisions-and-risks.md).

## Contents

| # | File | Covers (deliverable #) |
|---|------|------------------------|
| 01 | [01-product.md](01-product.md) | Product summary, MVP boundaries, personas, journeys (1, 2) |
| 02 | [02-screens-and-navigation.md](02-screens-and-navigation.md) | Information architecture, navigation, screen-by-screen requirements (3, 4) |
| 03 | [03-content.md](03-content.md) | Lesson schema, authoring format, editorial checklist, initial library (5) |
| 04 | [04-data-model.md](04-data-model.md) | Entities, relationships, constraints, indexes (6) |
| 05 | [05-api.md](05-api.md) | REST API with schemas, errors, idempotency, examples (7) |
| 06 | [06-architecture.md](06-architecture.md) | Backend and mobile project structures, responsibilities (8) |
| 07 | [07-learning-engine.md](07-learning-engine.md) | Spaced repetition, progress states, mastery, XP, streaks, achievements (9) |
| 08 | [08-ai-explanations.md](08-ai-explanations.md) | AI workflow, safeguards, limits, cost tracking (10) |
| 09 | [09-security-privacy.md](09-security-privacy.md) | Auth, authorization, privacy, deletion, security controls (11) |
| 10 | [10-design-system.md](10-design-system.md) | Tokens, components, interaction states (12) |
| 11 | [11-testing-acceptance.md](11-testing-acceptance.md) | Test strategy, feature-level acceptance criteria (13) |
| 12 | [12-analytics-validation.md](12-analytics-validation.md) | Event model, metric definitions, hypotheses (14) |
| 13 | [13-operations.md](13-operations.md) | Environments, config, deployment, operations (15) |
| 14 | [14-deferred-features.md](14-deferred-features.md) | Deferred features and the conditions for adding them (16) |
| 15 | [15-decisions-and-risks.md](15-decisions-and-risks.md) | Decisions that need approval, assumptions, risks, dependencies |

## Conventions used in this spec

- **MUST / SHOULD / MAY** follow RFC 2119 meaning.
- Requirement IDs: `FR-<area>-<n>` (functional), `AC-<area>-<n>` (acceptance criterion), `D-<n>` (decision for approval), `R-<n>` (risk).
- Areas: `AUTH`, `ONB` (onboarding), `DISC` (Discover), `LIB` (library), `LRN` (lesson player), `REC` (Recall), `AI`, `GAM` (gamification), `PROF` (profile/settings), `CNT` (content), `PRIV` (privacy), `OPS`.
- All timestamps are stored and sent as UTC ISO-8601 (`2026-10-18T09:30:00Z`). A "**local date**" is the calendar date in the user's stored IANA timezone. Streaks, daily goals, and review due dates are all computed on local dates.
- IDs are UUIDv7 unless stated otherwise. They sort by creation time and are safe to expose.
- Money is stored as integer **micro-USD** (1 USD = 1,000,000).

## Glossary

| Term | Meaning |
|------|---------|
| **Lesson** | The editorially reviewed unit of instruction. In the MVP, each lesson teaches exactly one **concept** (D-3), so "concept" and "lesson" refer to the same entity in storage. |
| **Lesson version** | An immutable snapshot of a lesson's content. Each attempt is pinned to one version. |
| **Attempt** | One pass through a lesson by a user, from start to completion. |
| **Lesson question** | A comprehension check inside the lesson flow (role `lesson`). |
| **Recall question** | A question used only in review sessions (role `recall`). It is never shown during the lesson. |
| **Review state** | Per-user, per-lesson scheduling data: ease, interval, repetitions, due date. |
| **Review session** | A batch of due review items answered in one sitting. |
| **Quality (q)** | The SM-2-style grade (1, 3 or 4) that a review answer maps to. |
| **Mastery stage** | A 0–4 integer derived from the review state. Displayed as progress dots. |
| **Learning-active day** | A local date on which the user answered at least one lesson or recall question. It is the basis for retention metrics. |
| **Streak day** | A local date on which the user completed a lesson attempt or a review session. |
| **Canonical content** | Lesson content written and reviewed by editors. AI output is never canonical. |

## Repository layout (target)

```
curiosity/
├── apps/
│   ├── api/            # FastAPI modular monolith (see 06-architecture.md)
│   └── mobile/         # Expo React Native app
├── content/            # Lesson source files (YAML) + media — the canonical content
├── docs/spec/          # This specification
├── docker-compose.yml  # Local Postgres + API
├── .github/workflows/  # CI
└── CLAUDE.md           # Pointer to this spec + working agreements (to be written)
```

Current state (commit `e7b2447`): `apps/api` and `apps/mobile` contain only `.gitkeep`, and `docker-compose.yml`, `.env.example` and `CLAUDE.md` are empty. The "FastAPI skeleton with health check" named in that commit message is not in the tree. Implementation therefore starts from scratch.
