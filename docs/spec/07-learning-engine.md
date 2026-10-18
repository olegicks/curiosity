# 07 — Learning Engine: Progress, Spaced Repetition, Mastery, XP, Streaks, Achievements

All rules in this file are executed **only on the backend**, inside the domain services in `app/learning`, `app/reviews` and `app/gamification`. The client displays results and never computes them. The rules are written as pure functions where possible, so they can be unit-tested with an injected clock.

## 7.1 Time and local dates

- `now` comes from an injectable `Clock` (production: system UTC; tests: a fixed clock).
- `local_today(user) = now.astimezone(ZoneInfo(user.preferences.timezone)).date()`.
- If the stored timezone is invalid or missing, fall back to `UTC`. Invalid values are rejected at `PATCH /me/preferences`.
- If a user changes timezone, existing `due_on`, streak dates, and daily activity dates keep their values. New computations use the new timezone. A one-day jump in either direction is accepted (R-7).

## 7.2 Progress states (viewed → completed → recalled → understood)

The app distinguishes these levels of evidence for each `(user, lesson)`:

| State | Definition (exact) | Stored as | What it proves |
|---|---|---|---|
| **Not started** | No `user_lesson_progress` row | — | Nothing |
| **Started** ("viewed") | An attempt was created (`POST /lessons/{slug}/attempts`) | `user_lesson_progress.first_started_at` | The user opened the lesson flow. It does **not** prove reading. |
| **Completed** | An attempt reached `completed`, meaning all lesson questions were answered and the summary was reached | `first_completed_at`, `completion_count` | Exposure, plus immediate comprehension checks (score recorded). |
| **Recalled** | At least one review with `quality ≥ 3`, taking place ≥ 1 day after first completion | `first_recalled_at` | Retrieval after a delay. |
| **Understood** | `review_states.repetitions ≥ 2`. Because of §7.3, this means two consecutive successful delayed reviews, the second after a ≥ 6-day interval, using recall questions different from the lesson's | `first_understood_at` (milestone); current state derived | Durable recall plus application to new scenarios. |
| **Retained** | `repetitions ≥ 3` (the latest success came after an interval of ≈ 15 days or more) | derived | Long-term retention. |

- Milestone timestamps (`first_*_at`) are **monotonic**. They are set once and never cleared, and they drive XP, achievements, and analytics.
- The **current** state can go down. After a failed review `repetitions` resets to 0, so a concept that was "understood" shows as "completed · needs review" until it is recalled again. This is intentional and transparent.
- "Demonstrated as understood" in product copy and metrics always refers to the definition above, never to lesson completion.

### Mastery stage (displayed as 4 dots)

```
mastery_stage(progress, review_state) =
  0  if not completed
  1  if completed and repetitions == 0      # "Learned"
  2  if repetitions == 1                    # "Recalled"
  3  if repetitions == 2                    # "Understood"
  4  if repetitions >= 3                    # "Retained"
```

In addition, the profile shows **recent recall accuracy**: the proportion of correct answers in the user's last 20 review events (or fewer if they have fewer), shown as "8 of last 10". No other mastery model exists in the MVP (no IRT, no probability estimates).

## 7.3 Spaced-repetition scheduler (`sm2-curiosity-v1`)

The scheduler is a pure module, `app/reviews/scheduler.py`, implementing:

```python
class Scheduler(Protocol):
    version: str
    def initial_state(self, completed_on: date) -> ReviewState: ...
    def grade(self, *, is_correct: bool, guessed: bool) -> int: ...          # → quality q
    def next_state(self, state: ReviewState, q: int, reviewed_on: date) -> ReviewState: ...
```

`ReviewState = (ease_factor: Decimal(3,2), interval_days: int, repetitions: int, lapses: int, due_on: date)`.

Every review state row stores `scheduler_version`, so a future algorithm can migrate or coexist without losing data.

### 7.3.1 Constants

| Name | Value |
|---|---|
| `EF_INITIAL` | 2.50 |
| `EF_MIN` | 1.30 |
| `EF_MAX` | 2.80 |
| `FIRST_INTERVAL` (after lesson completion) | 1 day |
| `SECOND_INTERVAL` (after the 1st successful review) | 6 days |
| `MAX_INTERVAL` | 180 days |
| `FAIL_EF_PENALTY` | 0.20 |
| `SESSION_MAX_ITEMS` | 20 |

### 7.3.2 Initial state (first lesson completion)

When an attempt completes **and** the user had no previous completion of that lesson, in the same transaction as completion:

```
ease_factor = 2.50, interval_days = 1, repetitions = 0, lapses = 0
due_on = local_today + 1 day
```

Revisiting a completed lesson (a later attempt) does **not** change the review state.

### 7.3.3 Response quality mapping

Each review item asks one objectively scored question. Multi-select is all-or-nothing.

| Outcome | Quality `q` | Meaning |
|---|---|---|
| Incorrect | **1** | Failed recall (lapse) |
| Correct, user toggled "I'm guessing" before checking | **3** | Hard pass |
| Correct | **4** | Good pass |

`q = 5` (SM-2's "perfect") and `q = 0, 2` are not produced by the MVP. The mapping is in `grade()` so that future signals (confidence scale, response time) can change it in one place. If the "I'm guessing" toggle is rejected (D-4), correct answers always map to 4.

### 7.3.4 State transition

```
next_state(s, q, reviewed_on):
  if q >= 3:                                   # success
      reps' = s.repetitions + 1
      if reps' == 1:   interval' = SECOND_INTERVAL                     # 6
      else:            interval' = ceil(s.interval_days * s.ease_factor)
      interval' = min(max(interval', s.interval_days + 1), MAX_INTERVAL)
      ef' = s.ease_factor + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))  # SM-2 formula
            # q=4 → +0.00 ; q=3 → -0.14
      lapses' = s.lapses
  else:                                        # failure (q = 1)
      reps' = 0
      interval' = FIRST_INTERVAL               # 1
      ef' = s.ease_factor - FAIL_EF_PENALTY
      lapses' = s.lapses + 1
  ef' = clamp(round_half_up(ef', 2), EF_MIN, EF_MAX)
  due_on' = reviewed_on + interval' days       # reviewed_on = local_today at answer time
```

Notes and rationale:
- The EF update for successes is the original SM-2 formula. For failures, a fixed −0.20 replaces SM-2's q=1 value (−0.54), which compounds too harshly with only three grades. Because the best grade available is q=4 (Δ = 0), ease never rises above 2.50 in v1. `EF_MAX` exists for future graders.
- From the 2nd success onwards, the next interval is `ceil(previous interval × EF)`, using the EF before this review's update. At EF 2.5 the intervals run 1 → 6 → 15 → 38 → 95 → 180 (cap).
- The `max(…, interval+1)` guard guarantees that intervals strictly grow after every success, even at low EF.
- **Late reviews:** the next interval is based on the *scheduled* interval, not on the actual elapsed time. The actual gap is recorded in `review_events.days_since_last_review` for analysis.
- **Early reviews** cannot happen. Only due items (`due_on ≤ local_today`) are offered.
- Within a session, a failed concept is **not** re-asked. It becomes due tomorrow.

### 7.3.5 Worked examples (these become unit-test fixtures)

| Step | Event | q | EF | interval | reps | lapses | due_on (completed Mon 2026-11-02) |
|---|---|---|---|---|---|---|---|
| 0 | Complete lesson | — | 2.50 | 1 | 0 | 0 | 2026-11-03 |
| 1 | Correct on 11-03 | 4 | 2.50 | 6 | 1 | 0 | 2026-11-09 |
| 2 | Correct (guessed) on 11-09 | 3 | 2.36 | ceil(6×2.50)=15 | 2 | 0 | 2026-11-24 |
| 3 | Incorrect on 11-24 | 1 | 2.16 | 1 | 0 | 1 | 2026-11-25 |
| 4 | Correct on 11-27 (2 days late) | 4 | 2.16 | 6 | 1 | 1 | 2026-12-03 |
| 5 | Correct on 12-03 | 4 | 2.16 | ceil(6×2.16)=13 | 2 | 1 | 2026-12-16 |

Note on step 2: the interval uses the EF *before* the update, `s.ease_factor`. This matches classic SM-2, where EF changes after computing the interval.

Edge fixtures: EF floor (repeated failures never take EF below 1.30); interval cap at 180; `interval+1` guard (EF 1.30, interval 1 → success with reps' ≥ 2 → max(ceil(1.3), 2) = 2).

### 7.3.6 Due reviews and session composition

- **Due** = `review_states.due_on ≤ local_today(user)` for lessons that are `published` or `retired`. Retired lessons stay reviewable until a later decision. If a retired lesson has no recall questions, it is excluded.
- `GET /reviews/summary.due_count` and session creation use the same repository function `due_review_states(user_id, local_today)`, so the counts always agree.
- **Session creation:** take due states ordered by `due_on ASC, first_completed_at ASC, lesson_id ASC`, and limit to `SESSION_MAX_ITEMS`.
- **Question selection per item:** choose uniformly at random among the lesson's `recall` questions (current published version), **excluding** `review_states.last_question_id` when more than one exists. Randomisation is seeded with `(session_id, lesson_id)` so it can be reproduced in tests. The chosen `question_id` is stored on the session item.
- **One open session per user** (DB-enforced). If an open session from a previous local date exists when a new one is requested, it is marked `expired` and a new one is created. Its unanswered items are still due, because answering is the only thing that changes due dates.
- **Answering an item** (one transaction):
  1. `SELECT … FOR UPDATE` the review state row.
  2. If the session item was already answered, return the stored result (idempotent replay).
  3. Grade the answer, compute `next_state`, update the review state, insert `review_events` (with before/after snapshots), and mark the item answered.
  4. Update `user_lesson_progress` milestones (`first_recalled_at`, `first_understood_at`).
  5. Apply gamification (§7.4–§7.6).
  6. If this was the last unanswered item, mark the session `completed` and apply session-completion XP.

## 7.4 XP rules

XP is a motivation signal, not a measure of learning. Each award is a row in `xp_transactions` with a **unique `(user_id, idempotency_key)`**. Awarding uses `INSERT … ON CONFLICT DO NOTHING` inside the business transaction, so repeated requests can never duplicate XP.

| Activity | XP | Idempotency key | Notes |
|---|---|---|---|
| First completion of a lesson | **20** | `lesson_complete:{lesson_id}` | Once per lesson, ever. Revisits earn 0. |
| Perfect first attempt (all lesson questions correct on the first completed attempt) | **+5** | `lesson_perfect:{lesson_id}` | Only on the attempt that first completes the lesson. |
| Review item answered correctly (q ≥ 3) | **5** | `review_item:{session_item_id}` | Items exist only when a concept is due, so this cannot be farmed. |
| Review item answered incorrectly | **1** | `review_item:{session_item_id}` | Rewards showing up and retrieving honestly. |
| Review session completed (all items answered) | **10** | `review_session:{session_id}` | |
| Daily goal reached | **10** | `daily_goal:{local_date}` | Awarded when the day's XP (excluding this bonus) first reaches the goal. |

Not rewarded: opening the app, viewing a lesson, in-lesson answers (beyond the completion and perfect bonuses), AI explanation requests, feedback submissions, and achievements (they carry no XP in the MVP).

- **Total XP** = `SUM(amount)` over the user's transactions (indexed). No cached counter, so there is nothing to drift.
- **Today's XP** = `SUM(amount) WHERE local_date = local_today`. `local_date` is stored on each transaction at award time.
- Daily goal options are 20 / 40 / 60 (D-9). Changing the goal mid-day applies immediately. If the new goal is already met, the bonus is awarded on the next XP-earning event that day (not retroactively at the moment of change).

## 7.5 Streaks

A **streak day** is a local date on which the user **completed a lesson attempt (including revisits) or completed a review session**. Answering a single review item without finishing the session does *not* count, but finishing a 1-item session does.

State is stored in `streak_states`: `current_streak`, `longest_streak`, `last_streak_date`, `freezes_available` (0–2), `freezes_used_total`.

**Freezes** protect against occasional misses:
- New users start with **1** freeze.
- A freeze is earned each time `current_streak` reaches a multiple of 7. Freezes are capped at 2.
- Freezes are consumed automatically. There is no purchase or manual action.

**On a qualifying event on local date D** (same transaction as the event):

```
if last_streak_date is None:              current = 1
elif D == last_streak_date:               no change
elif D == last_streak_date + 1:           current += 1
else:
    missed = (D - last_streak_date).days - 1
    if missed <= freezes_available:       freezes_available -= missed; freezes_used_total += missed; current += 1
    else:                                 current = 1
last_streak_date = D
longest = max(longest, current)
if current changed and current % 7 == 0:  freezes_available = min(2, freezes_available + 1)
```

**Displayed streak (read time, no background job):**

```
gap_missed = (local_today - last_streak_date).days - 1
if last_streak_date is None:                    display 0
elif local_today == last_streak_date:           display current  ("done today")
elif gap_missed <= freezes_available:           display current  ("keep it going today"; if gap_missed ≥ 1 show "a freeze will cover yesterday")
else:                                           display 0 (the stored value resets on next qualifying event)
```

Copy is supportive ("Welcome back — let's start a new streak"). The app never shows "You lost your 30-day streak!" dialogs.

## 7.6 Achievements

The definitions live in code (`app/gamification/achievements.py`) as an immutable registry. Only earned rows are stored (`user_achievements`, PK `(user_id, code)` → idempotent). They are evaluated synchronously after the triggering event in the same transaction.

| Code | Title | Condition | Trigger |
|---|---|---|---|
| `first_lesson` | First step | 1 lesson completed | lesson completion |
| `five_lessons` | Getting the picture | 5 distinct lessons completed | lesson completion |
| `topic_complete` | Topic explored | All published lessons in any one topic completed | lesson completion |
| `first_recall` | It stuck | First successful review (q ≥ 3) | review answer |
| `first_understood` | Understood | First concept reaches stage 3 | review answer |
| `ten_understood` | Deep understanding | 10 concepts have *ever* reached stage 3 (`first_understood_at` set) | review answer |
| `streak_7` | One week | `current_streak` reaches 7 | streak update |
| `reviews_10` | Habit of recall | 10 review sessions completed | session completion |

Responses that cause an unlock include `achievements_unlocked: [...]`, so the client can celebrate them with a subtle animation (no full-screen takeover).

## 7.7 Daily activity

`daily_activity (user_id, local_date)` is upserted in the same transactions as XP and answers. Columns: `lesson_questions_answered`, `review_items_answered`, `lessons_completed`, `review_sessions_completed`, `xp_earned`. It serves streak computation, retention metrics ([12](12-analytics-validation.md)), and the export. It is not a separate source of truth for XP: `xp_earned` is a denormalised convenience value and is verified against transactions in tests.

## 7.8 Recommendation rules

Deterministic and explainable. Computed in `app/learning/recommendations.py`.

1. **Candidate set:** published lessons the user has **not completed**.
2. **Eligibility:** all `prerequisites` completed. If no candidate is eligible, ignore prerequisites.
3. **Ordering key:**
   1. lessons in topics matching the user's interests first (if any interests are set);
   2. then topic order (`topics.position`), then `lessons.position`;
   3. lessons that are `related` to the most recently completed lesson are moved to the front of the list (max 1 boost).
4. **Today's lesson** = first candidate. **Recommended** = next 4.
5. **Primary action** (Discover) follows the priority in [02 §2.5](02-screens-and-navigation.md#25-discover-home).
6. **Next lesson** on the completion screen = the first `related` lesson not yet completed, otherwise today's lesson recomputed, otherwise none ("You've completed every lesson").

"Today's lesson" stays stable within a local day as long as the user hasn't completed it. Because it is recomputed from state each time, it changes once the user completes it.
