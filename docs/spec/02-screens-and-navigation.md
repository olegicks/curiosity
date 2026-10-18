# 02 — Information Architecture, Navigation and Screens

## 2.1 Information architecture

```
Root
├── Auth stack (shown when there is no session)
│   ├── Welcome
│   ├── Login
│   ├── Forgot password
│   └── Reset password (deep link curiosity://reset?token=…)
├── Onboarding stack (shown once after a guest session is created; skippable)
│   ├── Interests
│   └── Daily goal
└── App
    ├── Tabs
    │   ├── Discover   (home)
    │   ├── Learn      (library)
    │   └── Recall     (badge = due count)
    ├── Lesson intro            (push from any tab)
    ├── Lesson player           (full-screen modal, tabs hidden)
    │   └── AI explanation sheet (bottom sheet)
    ├── Review session          (full-screen modal, tabs hidden)
    ├── Profile                 (push, opened from avatar button in Discover header)
    │   ├── Achievements
    │   └── Settings
    │       ├── Account (create account / change password / logout)
    │       ├── Learning (daily goal, interests)
    │       ├── Appearance (System / Light / Dark)
    │       ├── Privacy (export data, delete account)
    │       └── About (version, content sources policy, disclaimer, licenses)
    └── Report a problem        (modal)
```

**Navigation rules**

- There are exactly three tabs. Profile and Settings are secondary and reachable only from the Discover header avatar.
- The lesson player and review session are modals. Closing one mid-way asks "Leave lesson? Your progress is saved." (no confirmation is needed once the flow is complete). Progress is saved server-side per answer, so leaving loses nothing.
- Implementation: **Expo Router** (file-based) with typed routes. Deep links: `curiosity://lesson/{slug}`, `curiosity://recall`, `curiosity://reset?token=…`.
- Android back button: inside the player it behaves like the close button (with the same confirmation). On tab roots it follows the default behaviour.

## 2.2 Global screen requirements

| ID | Requirement |
|---|---|
| FR-GLB-1 | Every screen that loads data has **loading** (skeleton, not spinner, for layout-heavy screens), **error** (message + Retry), and, where applicable, **empty** states. |
| FR-GLB-2 | When the device is offline, a non-blocking banner reads "You're offline. Some actions are unavailable." Cached read-only data (Discover, library, lesson content already fetched) stays visible. Answer submission, attempt start, and AI buttons are disabled with an explanation. |
| FR-GLB-3 | Errors from the API are mapped by `error.code` to user-facing copy. Raw messages and stack traces are never shown. |
| FR-GLB-4 | An expired access token is refreshed transparently once. If refresh fails, the user is returned to Welcome with the message "Please sign in again." (For guests whose refresh fails the guest account can't be recovered. Copy: "Your guest session expired.") |
| FR-GLB-5 | All touch targets are ≥ 44×44 pt. All interactive elements have accessibility labels and roles. |
| FR-GLB-6 | If the API returns `426 UPGRADE_REQUIRED`, a blocking screen asks the user to update the app. |

## 2.3 Welcome
- Content: app name, one-sentence value proposition, a small editorial illustration, **Start learning** (primary), **I already have an account** (secondary), and links to Terms and Privacy Policy.
- FR-ONB-1: **Start learning** creates a guest account (`POST /v1/auth/guest`) and sends `timezone` from `Intl.DateTimeFormat().resolvedOptions().timeZone`. On network failure: error state with Retry. No account is created locally.

## 2.4 Onboarding
- FR-ONB-2: **Interests** has three selectable cards (multi-select, 0–3) mapped to topic slugs (see [03 §3.6](03-content.md#36-initial-library)). Buttons: Continue / Skip. Saved via `PATCH /v1/me/preferences`.
- FR-ONB-3: **Daily goal** offers Light 20 XP ("about one lesson") / Steady 40 / Ambitious 60. Default is preselected as Light. Buttons: Continue / Skip.
- FR-ONB-4: After onboarding the user lands on the **lesson intro** of the top recommendation, not on Discover.
- FR-ONB-5: Onboarding is shown at most once per account (`preferences.onboarding_completed_at`). Skipping counts as completing it.
- Display name is not asked during onboarding. It is optional when upgrading the account.

## 2.5 Discover (home)

Purpose: make the next useful action obvious.

**Layout (top to bottom)**
1. Header: greeting ("Good morning" by local time + display name if set), compact **streak** (🔥-style icon + count) and **today's XP vs goal** ring, avatar button → Profile.
2. **Primary action card**, chosen by this priority:
   1. Reviews due ≥ 1 → "Review N concepts · ~M min" → Review session.
   2. An in-progress lesson attempt exists → "Continue: <title> · step x of y" → Lesson player (resume).
   3. Otherwise → "Today's lesson: <title>" with the one-line description → Lesson intro.
   4. All lessons completed and none due → "You're all caught up. Next review <weekday/date>." with a secondary "Revisit a lesson" link to the Library.
3. **Today's lesson** card (shown only when the primary card is not already today's lesson): the top recommendation.
4. **Recommended for you**: horizontal list of up to 4 further recommendations (lesson cards).
5. **Your progress** strip: "X of N concepts learned · Y understood" with a thin progress bar → tap opens Profile.

FR-DISC-1: All data comes from one call, `GET /v1/discover`. The server computes the primary action and recommendations (algorithm in [07 §7.8](07-learning-engine.md#78-recommendation-rules)).
FR-DISC-2: Pull-to-refresh refetches. The data also refetches when the app returns to the foreground or the local date changes.
FR-DISC-3: No more than 5 content blocks. No charts.
States: skeleton loading; error with Retry; a new user sees the onboarding recommendation as today's lesson and progress "0 of N".

## 2.6 Learn tab (library)
- Lessons grouped by topic (section headers in curated order). Each row shows title, one-line description, ~minutes and a **status indicator**: not started (empty circle) · in progress (half) · completed (filled) · mastery dots (0–4) once completed.
- A filter chip row: All · Not started · In progress · Completed. This is client-side filtering of a list the server already returned.
- FR-LIB-1: `GET /v1/lessons?limit=100` returns all published lessons with the caller's progress. The client groups them by `topic`.
- FR-LIB-2: Tap → Lesson intro.
- Empty state (only if no lessons are published, which is an operational error): "Lessons are on their way."

## 2.7 Lesson intro
- Title, topic, learning objective ("After this lesson you can…"), estimated minutes, status/mastery, related lessons, and an evidence note if the lesson is marked `contested` ("Parts of this topic are debated by researchers — the lesson explains how.").
- Primary button: **Start** / **Continue** (if an attempt is in progress) / **Revisit** (if completed). Revisit creates a new attempt but awards no completion XP again. The screen tells the user this: "Revisiting won't change your review schedule."
- FR-LRN-1: `GET /v1/lessons/{slug}` provides the intro data. The full step content may be prefetched for offline reading, but answers are never included.

## 2.8 Lesson player (the "Learn screen")

**Structure**: a horizontal progress bar (step x of y), a close button, and the step content. One step at a time, advanced with a **Continue** button. Swiping is not used, to avoid accidental skips. A **Back** control lets the user re-read previous content steps. Answered questions can be revisited read-only and cannot be re-answered.

**Step types** (from the content schema, [03 §3.2](03-content.md#32-lesson-schema)):

| Step | Rendering | Interaction |
|---|---|---|
| `hook` | Large serif question or scenario, optional illustration | Continue |
| `explanation` | Reading layout (serif body, max ~65 chars/line), optional illustration with alt text | Continue · **Explain differently** (AI) |
| `example` | Card with label "Example" + `illustrative`/`from research` tag; research examples show a source chip | Continue · Explain differently |
| `misconception` | "Common misconception" card: myth → correction | Continue |
| `evidence` | "What the research says" card with status badge (Established / Debated) | Continue |
| `question` | Prompt, options (single choice: radio-style cards; multi-select: checkbox cards + "Select all that apply"; true/false: two large buttons) | Select → **Check** → feedback → Continue |
| `summary` | Key takeaway bullets (2–4) | Continue → completion screen |

**Question feedback (FR-LRN-4)**
- After **Check**, the client calls `POST /v1/attempts/{id}/answers`. The **Check** button shows a pressed/loading state, and options are locked as soon as it is tapped.
- Correct: the selected option is highlighted in the success colour with a check icon, a success haptic plays, and the panel reads "Correct" plus the explanation.
- Incorrect: the selected option is shown in the danger colour with an ✕ icon, the correct option(s) are outlined in success, and the panel reads "Not quite" plus the selected option's feedback and the general explanation.
- Colour is never the only signal: icons and text labels are always present.
- If the request fails (network or 5xx), the options are unlocked and the error is shown inline with Retry. No local grading takes place.

**Completion (FR-LRN-6)**
- When the user continues past the summary, the client calls `POST /v1/attempts/{id}/complete` and shows the completion screen: takeaway, score on first try, XP breakdown, "First review: tomorrow" (only for first completion), achievements unlocked (max 2 shown, rest in Profile), optional "Was this lesson clear?" 👍/👎, **Next: <related lesson title>** (primary), and **Finish** (secondary, returns to the screen the user came from).

**Other requirements**
- FR-LRN-2: Content is rendered from structured JSON, never HTML. Markdown subset: paragraphs, **bold**, *italic*, bullet lists, and inline links to `sources` only.
- FR-LRN-3: The player restores position when resumed. The position is derived from answered questions plus a client-stored step index for content steps (non-authoritative, `AsyncStorage`, keyed by attempt ID).
- FR-LRN-5: Overflow menu: Report a problem · Sources (lists the lesson's references with links).
- FR-LRN-7: Text scales with OS settings up to at least 200% without clipping. Long content scrolls within the step.

## 2.9 AI explanation sheet
- Mode buttons: **Simpler** · **Practical example** · **Analogy**.
- Result panel: a distinct surface colour plus an "AI-generated" badge and the persistent caption "Generated from this lesson. May contain mistakes. The lesson above is the reviewed version." It never visually merges with canonical content.
- Actions: Another version · 👍 Helpful · 👎 Not helpful · ⚑ Incorrect · Close.
- States: loading (skeleton text lines + "Writing an explanation…", cancel allowed), error (`AI_UNAVAILABLE`, `AI_DISABLED`), limit reached (`AI_RATE_LIMITED`: "You've used today's alternative explanations. They reset at midnight."), offline (buttons disabled).
- FR-AI-UI-1: Remaining daily requests are shown subtly ("7 left today") once fewer than 5 remain.

## 2.10 Recall tab
- Header: "Recall"; a summary card showing due today (N), next due date if none, and total concepts in review.
- Primary button: **Start review (N)**, or **Resume review** if an open session exists.
- Below: a "Concepts in review" list sorted by next due date, showing title, mastery dots, and "due today / in 3 days". Tap → Lesson intro (to re-read, not to review).
- Empty states: no completed lessons ("Complete a lesson to start building your memory. Reviews appear the day after you learn something.") with a link to Discover; nothing due ("All caught up. Next review: Thursday.").
- FR-REC-1: Data from `GET /v1/reviews/summary` and `GET /v1/reviews/concepts`.

## 2.11 Review session
- Progress bar (item x of N), close button (confirm "End review? Answered items are saved."), and the item.
- Item: a small concept label ("Concept: Anchoring"), shown by default because recall here is concept-specific application and not concept identification (D-4 notes this choice), then the question and options. Optional **"I'm guessing"** toggle (D-4), then **Check**.
- Feedback: correct/incorrect (same visual language as lessons), explanation, the scheduling result ("See you again in 6 days" / "We'll bring this back tomorrow"), mastery dots animated to their new value, and a link "Revisit lesson" when the answer was incorrect.
- Session summary: correct/total, XP earned, concepts that advanced, concepts to revisit, streak update. Buttons: **Done**.
- FR-REC-2: Items come from the server snapshot (`POST /v1/review-sessions`). The client never decides due items.
- FR-REC-3: When the user ends early, the client calls `POST /v1/review-sessions/{id}/end`.

## 2.12 Profile
- Display name (or "Guest learner" with a **Save your progress** card for guests), total XP, current and longest streak, freezes available ("1 streak freeze ready"), concept counts by stage (Learned / Recalled / Understood / Retained), recent recall accuracy ("8 of last 10 correct"), and an achievements preview (earned + locked, max 8 total).
- No charts or historical graphs in the MVP.

## 2.13 Settings
- **Account**: guest → Create account; full → email (read-only), Change password, Log out.
- **Learning**: daily goal, interests.
- **Appearance**: System / Light / Dark (stored on the device only).
- **Privacy**: Export my data (shares a JSON file via the OS share sheet), Delete account (J7).
- **About**: version, build, "How we choose sources", educational disclaimer, open-source licenses.
- Logout as a guest warns: "Guest progress can't be recovered after logging out. Create an account first?" (Create account / Log out anyway).
