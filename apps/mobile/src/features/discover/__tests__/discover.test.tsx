import { fireEvent, render, screen } from "@testing-library/react-native";

import type { DiscoverOut, LessonSummary } from "@/api/types";
import {
  greeting,
  primaryCard,
  showTodaysLessonCard,
  streakA11yLabel,
} from "@/features/discover/discover";
import { DiscoverView } from "@/features/discover/DiscoverView";
import { strings } from "@/i18n/en";
import { ThemeProvider } from "@/ui/theme";

const lesson = (slug: string, title: string): LessonSummary => ({
  slug,
  title,
  description: `${title} description`,
  topic: { slug: "judgment", title: "Judgment" },
  estimated_minutes: 5,
  evidence_status: "established",
  position: 1,
  progress: {
    status: "not_started",
    mastery_stage: 0,
    completed_at: null,
    next_review_on: null,
    in_progress_attempt_id: null,
  },
});

const anchoring = lesson("anchoring", "Anchoring");
const framing = lesson("framing", "Framing");

function discover(overrides: Partial<DiscoverOut> = {}): DiscoverOut {
  return {
    local_date: "2026-11-02",
    primary_action: { type: "start_lesson", lesson: anchoring },
    todays_lesson: anchoring,
    recommended: [framing],
    progress: { lessons_total: 27, completed: 4, understood: 1 },
    streak: { current: 3, longest: 5, freezes_available: 1, done_today: false, at_risk: true },
    xp: { today: 15, goal: 20, total: 140 },
    reviews_due: 0,
    ...overrides,
  };
}

describe("discover helpers", () => {
  test("greeting follows the time of day", () => {
    expect(greeting(8, "Maya")).toBe("Good morning, Maya");
    expect(greeting(14, null)).toBe("Good afternoon");
    expect(greeting(21, null)).toBe("Good evening");
    expect(greeting(2, null)).toBe("Good evening");
  });

  test("primary card for each server action", () => {
    const review = primaryCard(
      discover({
        primary_action: {
          type: "review",
          review: { due_count: 5, estimated_minutes: 3, open_session_id: null },
        },
        reviews_due: 5,
      }),
      "2026-11-02",
    );
    expect(review.title).toBe("Review 5 concepts · ~3 min");
    expect(review.destination).toEqual({ kind: "review" });

    const resume = primaryCard(
      discover({
        primary_action: {
          type: "review",
          review: { due_count: 1, estimated_minutes: 1, open_session_id: "s1" },
        },
      }),
      "2026-11-02",
    );
    expect(resume.title).toBe("Review 1 concept · ~1 min");
    expect(resume.cta).toBe(strings.recall.resume);

    const cont = primaryCard(
      discover({ primary_action: { type: "continue_lesson", lesson: framing, attempt_id: "a1" } }),
      "2026-11-02",
    );
    expect(cont.destination).toEqual({ kind: "play", slug: "framing" });

    expect(primaryCard(discover(), "2026-11-02").destination).toEqual({
      kind: "lesson",
      slug: "anchoring",
    });

    const caughtUp = primaryCard(
      discover({ primary_action: { type: "caught_up", next_review_on: "2026-11-05" } }),
      "2026-11-02",
    );
    expect(caughtUp.body).toBe("Next review Thursday.");
    expect(caughtUp.destination).toEqual({ kind: "learn" });
  });

  test("today's lesson card is not repeated under the primary card", () => {
    expect(showTodaysLessonCard(discover())).toBe(false);
    expect(
      showTodaysLessonCard(
        discover({ primary_action: { type: "continue_lesson", lesson: framing } }),
      ),
    ).toBe(true);
    expect(showTodaysLessonCard(discover({ todays_lesson: null }))).toBe(false);
  });

  test("streak labels are supportive", () => {
    expect(streakA11yLabel(discover())).toBe("3-day streak, learn today to keep it");
    expect(
      streakA11yLabel(
        discover({
          streak: {
            current: 0,
            longest: 2,
            freezes_available: 1,
            done_today: false,
            at_risk: false,
          },
        }),
      ),
    ).toBe(strings.discover.noStreak);
  });
});

test("Discover shows the next action, signals and recommendations", async () => {
  const onNavigate = jest.fn();
  const onOpenProfile = jest.fn();
  await render(
    <ThemeProvider>
      <DiscoverView
        discover={discover({ primary_action: { type: "continue_lesson", lesson: framing } })}
        displayName="Maya"
        now={new Date(2026, 10, 2, 9, 0)}
        onNavigate={onNavigate}
        onOpenProfile={onOpenProfile}
      />
    </ThemeProvider>,
  );
  expect(screen.getByText("Good morning, Maya")).toBeOnTheScreen();
  expect(screen.getByLabelText("3-day streak, learn today to keep it")).toBeOnTheScreen();
  expect(screen.getByLabelText("15/20 XP today")).toBeOnTheScreen();
  expect(screen.getByText(strings.discover.continueEyebrow)).toBeOnTheScreen();
  expect(screen.getByText(strings.discover.todaysLesson.toUpperCase())).toBeOnTheScreen();
  expect(screen.getByText(strings.discover.recommended.toUpperCase())).toBeOnTheScreen();

  await fireEvent.press(screen.getByRole("button", { name: strings.lessons.continue }));
  expect(onNavigate).toHaveBeenCalledWith({ kind: "play", slug: "framing" });

  await fireEvent.press(screen.getByRole("button", { name: /^Framing\./ }));
  expect(onNavigate).toHaveBeenLastCalledWith({ kind: "lesson", slug: "framing" });

  await fireEvent.press(screen.getByRole("button", { name: strings.discover.progress(4, 27, 1) }));
  expect(onOpenProfile).toHaveBeenCalled();
});
