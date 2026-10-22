# 10 — UI Design System and Interaction States

## 10.1 Design direction

> **Superseded by D-16 (2026-10-22).** The app now uses a playful, game-like direction: a learning path on the home tab, a bright palette with one colour per unit, bold sans type for headings, chunky buttons with a darker bottom edge, icons, and a celebratory completion screen with a short confetti burst. `src/ui/tokens.ts` is the source of truth for the new tokens. Accessibility rules in this file still apply unchanged (AA contrast, colour never the only signal, text scaling, reduce motion). The text below records the original direction.

**Editorial, calm, intelligent.** The app should feel like a well-edited magazine for ideas, not a game for children and not a generic AI dashboard.

- Warm paper-like backgrounds, ink-coloured text, one confident accent colour.
- A serif for reading and headings, and a clean sans for UI controls.
- Generous whitespace. One primary action per screen.
- Illustrations: simple, flat, limited palette (accent + ink + one neutral), used to clarify a concept (a diagram of an anchor scale, two framing options side by side), not to decorate.
- Avoid: gradients (except the subtle skeleton shimmer), drop-shadow-heavy cards, confetti, badge walls, mascots, aggressive red counters.

## 10.2 Tokens (`src/ui/tokens.ts`)

### Colour (contrast ratios measured against `bg`/`surface`; all body and UI text ≥ 4.5:1)

| Token | Light | Dark | Use | Contrast (light / dark, vs bg) |
|---|---|---|---|---|
| `bg` | `#FAF7F2` | `#14130F` | App background | — |
| `surface` | `#FFFFFF` | `#1E1C18` | Cards, sheets | — |
| `surfaceMuted` | `#F1ECE3` | `#2A2721` | Example/misconception cards, skeletons | — |
| `border` | `#E3DDD2` | `#38342C` | Dividers, option outlines (non-text) | — |
| `text` | `#1F1D1A` | `#EDE9E1` | Primary text | 15.7 / 15.4 |
| `textMuted` | `#5F5A52` | `#A8A196` | Secondary text | 6.4 / 7.3 |
| `accent` | `#3346A8` | `#9AA8F2` | Primary buttons, links, progress | 7.6 / 8.2 |
| `onAccent` | `#FFFFFF` | `#14130F` | Text on accent | 8.1 / 8.2 |
| `success` | `#24704A` | `#6CC596` | Correct state | 5.6 / 8.9 |
| `danger` | `#B23A2A` | `#F08A78` | Incorrect state, destructive actions | 5.6 / 7.6 |
| `ai` | `#7A4BA8` | `#C6A2EC` | AI badge, AI panel border | 5.8 / 8.7 |
| `successBg` / `dangerBg` / `aiBg` | 10% tint of the colour over `surface` | 16% tint over `surface` | Feedback panel backgrounds | text on these stays `text` |

Colour is never the only signal. Correct and incorrect states always include an icon and a text label.

### Typography

| Token | Font | Size / line height (pt) | Use |
|---|---|---|---|
| `display` | Source Serif 4 Semibold | 30 / 36 | Hook question, completion heading |
| `title` | Source Serif 4 Semibold | 24 / 30 | Screen titles, lesson title |
| `heading` | Inter Semibold | 18 / 24 | Card titles, section headers |
| `reading` | Source Serif 4 Regular | 18 / 28 | Lesson body text |
| `body` | Inter Regular | 16 / 24 | UI text, options, feedback |
| `label` | Inter Medium | 14 / 20 | Buttons, chips, metadata |
| `caption` | Inter Regular | 13 / 18 | AI caption, source chips |

Both fonts are OFL-licensed and bundled through `@expo-google-fonts`. Text scales with the OS setting. `reading` and `body` support at least 200%. UI chrome (tab labels, badges) uses `maxFontSizeMultiplier` 1.5 so the layout doesn't break, and long content scrolls instead of clipping. The reading measure is capped at about 65 characters per line (max width 600 pt).

### Spacing, radius, elevation, motion

- Spacing scale (4-pt grid): `xs 4 · sm 8 · md 12 · lg 16 · xl 24 · 2xl 32 · 3xl 48`. Screen horizontal padding is `lg` (16), or `xl` (24) on wide phones.
- Radius: `sm 6` (chips), `md 12` (cards, options), `lg 20` (sheets), `full` (pills, avatar).
- Elevation: flat by default. Sheets get one soft shadow. In dark mode, elevation is shown with `surface` steps instead of shadows.
- Motion: `fast 120 ms` (press feedback), `base 200 ms` (state change, feedback panel reveal), `slow 320 ms` (sheet, mastery dot fill). Easing is standard ease-out. When the OS "reduce motion" setting is on, animations become instant crossfades.
- Haptics: light impact on option select, success notification on correct, warning notification on incorrect. Haptics respect the system settings.

## 10.3 Core components (`src/ui`)

| Component | Variants / props | States |
|---|---|---|
| `Button` | primary, secondary, ghost, destructive. sizes md/lg | default, pressed, disabled, loading (spinner + label kept for width) |
| `Card` | plain, muted, interactive | default, pressed |
| `LessonCard` | compact (list row), feature (Discover) | with status / mastery |
| `PrimaryActionCard` | review, continue, start, caught_up | loading skeleton |
| `OptionCard` | single (radio), multi (checkbox), true/false | idle, selected, locked, correct, incorrect, correct-not-selected (outlined) |
| `FeedbackPanel` | correct, incorrect | animated reveal. Contains explanation + per-option feedback |
| `ProgressBar` | lesson steps, session items, topic progress | determinate |
| `MasteryDots` | 0–4 | animated fill on change. Accessible label "Mastery: Understood, 3 of 4" |
| `StreakBadge` | done today / pending / at risk (subtle) | |
| `XpRing` | today vs goal | goal reached state |
| `AiBadge` + `AiPanel` | ai_generated, ai_reviewed | loading, error, limit |
| `Banner` | offline, info, error | dismissible (info only) |
| `EmptyState` | illustration + title + body + optional action | |
| `Skeleton` | text lines, card, list | shimmer (static if reduce motion) |
| `Sheet` | bottom sheet with drag handle | |
| `Markdown` | restricted subset renderer | |

Each component has a Jest/RNTL test for its accessibility label and role and for its state rendering.

## 10.4 Essential interaction states

| Situation | Behaviour |
|---|---|
| **Select option** | Instant selected state (≤ 100 ms). The Check button becomes enabled. Multi-select shows the count ("2 selected"). |
| **Check pressed** | Options lock and the button shows loading. On success the FeedbackPanel slides in (200 ms) and the button turns into Continue. On failure, an inline error appears and the options unlock. |
| **Correct** | Selected option in `success` with ✓ and "Correct" label, panel in `successBg`, success haptic. |
| **Incorrect** | Selected option in `danger` with ✕, correct option outlined in `success` with "Correct answer" label, panel in `dangerBg`, warning haptic. The tone is encouraging ("Not quite — here's why"). |
| **XP gained** | A small "+5 XP" chip fades up near the progress bar (no sound). |
| **Mastery change** | Dots fill or empty with the `slow` animation, plus text ("Now: Understood"). |
| **Achievement** | A compact toast-like card on completion or summary screens, max 2 at a time. |
| **Loading (screen)** | Skeletons shaped like the final layout. A spinner only inside buttons. |
| **Empty** | `EmptyState` with a helpful next action (see screen specs). |
| **Error (screen)** | "Something went wrong" + Retry. Specific copy for known codes. |
| **Offline** | Persistent top banner. Disabled actions show "Needs connection" on tap. |
| **Long text** | Steps scroll. The Continue button is fixed at the bottom with a safe-area inset. |
| **Session expired** | Return to Welcome with an explanation (FR-GLB-4). |

## 10.5 Accessibility requirements

- WCAG 2.2 AA as the target: contrast as above, touch targets ≥ 44 pt, focus order matching visual order, no information conveyed by colour alone.
- VoiceOver and TalkBack: every control labeled. Option cards announce "Option 2 of 4, selected" and after checking "correct" or "incorrect". FeedbackPanel content is announced via an accessibility live region.
- Dynamic Type as specified in §10.2. Layouts are tested at 200% on a small phone (iPhone SE size) and on Android at the largest font setting.
- No time limits on questions or reviews.
- Images have alt text from content. Decorative images are hidden from screen readers.
- Light, dark, and system themes. The theme follows the system by default and can be overridden in Settings.
