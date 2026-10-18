# 01 — Product Summary, Boundaries, Personas and Journeys

## 1.1 Product summary

**Curiosity** helps people understand complex ideas, remember them over time, and recognize them in real situations. The core loop is:

```
Discover ──► Learn (one concept, explained + checked) ──► Recall (spaced, active, scored) ──┐
   ▲                                                                                      │
   └──────────────────────────── progress, streak, next recommendation ◄──────────────────┘
```

**Value proposition:** *Understand an idea, test your understanding, and remember what you learn.*

**How it differs from alternatives**

| Alternative | Its weakness | What Curiosity does instead |
|---|---|---|
| Social media / video explainers | Passive, shallow, nothing checks whether you understood | Short lessons with mechanism, misconceptions and comprehension checks with explained feedback |
| Flashcard apps | Users write their own cards; cards test definitions, not understanding | Reviewed content and scenario-based recall questions on a built-in schedule |
| General AI chatbots | Unverified, no curriculum, no memory of what you learned | Canonical reviewed lessons. AI only re-explains them, and the output is labeled. |
| Long online courses | High commitment, low completion | 5–8 minute lessons, one concept each, with a clear next step |

**Initial subject:** Psychology → cognitive biases and the foundational ideas behind them (heuristics, dual-process accounts, basic statistical reasoning).

**Working name:** "Curiosity". Branding and trademark checks do not block the MVP. The app name, bundle IDs and display strings come from configuration so the name can be changed later (`APP_DISPLAY_NAME`; bundle ID chosen at first store submission).

## 1.2 MVP boundaries

### In scope

1. Account system with **guest-first** access, an upgrade path to email and password, login, logout, password reset and account deletion (D-1, D-2).
2. Lightweight onboarding: interests (optional), daily goal (optional), then straight into the first lesson.
3. **Discover**: one primary next action, today's lesson, recommended lessons, reviews due, basic progress, and a compact streak/XP summary.
4. **Learn**: a library grouped by topic, plus a lesson player with hook, explanation, examples, misconceptions, interleaved comprehension questions with explained feedback, a completion summary and a related next lesson.
5. **Recall**: review sessions over due concepts, built on a documented SM-2-inspired scheduler with mastery stages.
6. **AI alternative explanations**: three modes (simpler, practical example, analogy). Results are cached, rate-limited, cost-tracked and clearly labeled.
7. **Gamification**: XP with transparent rules, a daily streak with freezes, a daily XP goal, and 8 milestone achievements.
8. **Content system**: lessons written as YAML in the repo, validated and imported into Postgres, versioned, with sources. Launch requires at least 20 published lessons (target 27).
9. Content feedback ("report a problem") and AI explanation feedback.
10. In-house product analytics events stored in Postgres.
11. Light and dark themes, accessibility basics, and offline/error/empty states.
12. iOS and Android phones (D-10).

### Out of scope (MVP)

AI grading of free text · conversational tutor · knowledge-graph visualization · ML recommendations · social features of any kind · leaderboards · user-created content · payments/subscriptions · additional subjects · complex achievement systems · analytics dashboards (SQL queries only) · push notifications · web app and tablet-specific layouts · microservices, Kubernetes, Redis, message brokers, workers · admin web UI (content goes through Git and a CLI) · social login (D-2) · offline lesson completion.

The reason for each exclusion and the conditions for adding it later are in [14-deferred-features.md](14-deferred-features.md).

### Product principles (tie-breakers for unclear cases)

1. **The next useful action is obvious.** Each screen has one primary action.
2. **The backend is the source of truth** for correctness, progress, scheduling and XP. The client never decides these.
3. **Understanding over engagement.** No XP for opening the app or repeating a solved question. Never reward speed over thought.
4. **Honesty about evidence.** Lessons distinguish established findings from contested ones. AI never claims to be canonical.
5. **Low pressure.** Streaks forgive occasional misses. No guilt-based copy. No notifications in the MVP.

## 1.3 Personas

### P1 — Maya, the curious student (primary)
- 20, undergraduate (not a psychology major), commutes, has 5–10 minutes at a time.
- Hears terms like "confirmation bias" online and wants to really understand them, beyond the meme version.
- **Needs:** short sessions, clear wording, proof she understood, some sense of progress.
- **Frustrations:** long courses, preachy content, apps that feel childish.
- **Success for Maya:** after two weeks she can name and explain 8+ biases and spot them in a news story.

### P2 — Daniel, the young professional (primary)
- 28, product analyst, makes decisions in meetings, likes non-fiction books but forgets most of them.
- **Needs:** practical implications ("how does anchoring affect a negotiation?"), retention without effort, a credible source behind each claim.
- **Frustrations:** pop-psych oversimplification and unsourced claims.
- **Success for Daniel:** recalls concepts weeks later and uses them at work.

### P3 — Ruth, the lifelong learner (secondary)
- 55, retired teacher, reads widely, moderately comfortable with tech, often uses larger text sizes.
- **Needs:** readable typography, text scaling, no time pressure, a calm interface.
- **Success for Ruth:** a relaxed daily habit with steady progress and no sense of competition.

**Non-target users for the MVP:** exam candidates who need syllabus coverage, children, and clinicians looking for clinical guidance. The content is educational, not clinical advice. A short disclaimer appears in the About screen.

## 1.4 Primary user journeys

Each journey lists its steps and the screens involved (see [02](02-screens-and-navigation.md)).

### J1 — First run to first lesson (target: the first lesson starts in 3 taps or fewer from the welcome screen)
1. User opens the app and sees **Welcome** (value proposition, "Start learning", "I already have an account").
2. Taps **Start learning**. The client calls `POST /v1/auth/guest`, stores the tokens, and sends the device timezone.
3. **Interests** (optional, skippable): pick 0–3 of "Decisions & money", "Thinking clearly", "People & society". This only affects lesson ordering.
4. **Daily goal** (optional, skippable): Light 20 XP / Steady 40 XP / Ambitious 60 XP (default Light).
5. Lands on the **lesson intro** for the first recommended lesson (normally *What is a cognitive bias?*) with a **Start** button.
6. Goes through the lesson player (J2).
7. After completion: a soft prompt "Save your progress" (upgrade account), which can be dismissed. Repeated at most once after the 3rd completed lesson and in Profile. Never blocking.

### J2 — Learn a concept
1. From Discover ("Today's lesson" / "Continue") or the Library, open the **lesson intro** (title, objective, ~minutes, status).
2. **Start**: `POST /v1/lessons/{slug}/attempts`, which returns the pinned content.
3. Steps are shown one at a time: hook → explanation → example(s) → misconception → questions interleaved where the author placed them → summary.
4. For each question: select → **Check** → server returns correctness plus per-option feedback → **Continue**.
5. At any explanation step: **"Explain differently"** opens the AI sheet (J4).
6. Final step: **completion summary** showing key takeaway, score (e.g. "3/3 on first try"), XP earned, the "first review: tomorrow" notice, achievements unlocked, an optional 👍/👎 "Was this clear?", **Next: <related lesson>** and **Finish**.

### J3 — Daily recall
1. Discover shows "**5 reviews due**" as the primary action (reviews come before new lessons). The Recall tab badge shows the same count.
2. Tap → `POST /v1/review-sessions`, which creates or resumes today's session (max 20 items).
3. Per item: a scenario/question about a previously learned concept (never the lesson's own questions), options, an optional "I'm guessing" toggle, then **Check**.
4. Feedback: correct/incorrect, explanation, "Next review in 6 days", mastery dots update.
5. After the last item: session summary showing correct count, XP, concepts that moved stage, and any that need more practice (with a "Revisit lesson" link). Back to Discover.
6. The user may **End session** early. Unanswered items stay due and nothing is lost.

### J4 — Ask for an alternative explanation
1. In a lesson step, tap **Explain differently**. A bottom sheet offers: *Simpler* · *Practical example* · *Analogy*.
2. Choose a mode → loading state → the explanation is shown in a panel visually separate from the lesson and labeled "AI-generated · may contain errors · based on this lesson".
3. Actions: **Another version** (cycles cached variants), 👍 / 👎 / "Incorrect", Close.
4. On failure or limit: an inline friendly message ("Alternative explanations are unavailable right now. The lesson itself is unaffected."). The lesson flow is never blocked.

### J5 — Save progress (guest → full account)
1. From the soft prompt or Profile → **Create account**: email, password, optional display name.
2. `POST /v1/auth/upgrade` turns the same user row into a full account. All progress stays, and the tokens are rotated.

### J6 — Return on a new device / after logout
1. Welcome → **I already have an account** → login → Discover with server-side progress restored.

### J7 — Delete account
1. Profile → Settings → **Delete account** → explanation of what is deleted → confirm (password required for full accounts; for guests, type `DELETE`) → `DELETE /v1/me` → back to Welcome with local storage wiped.

### J8 — Report a content problem
1. In any lesson step or recall feedback: overflow menu → **Report a problem** → kind (factual error / unclear / typo / other) + optional text (≤ 500 chars) → submit → "Thanks — our editors review every report."
