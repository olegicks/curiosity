import { fireEvent, render, screen } from "@testing-library/react-native";

import type { DiscoverOut, LessonSummary, ProgressBrief } from "@/api/types";
import {
  buildPath,
  currentSlug,
  nodeIcon,
  nodeOffset,
  streakA11yLabel,
} from "@/features/path/path";
import { PathView } from "@/features/path/PathView";
import { strings } from "@/i18n/en";
import { ThemeProvider } from "@/ui/theme";

const lesson = (
  slug: string,
  topic: string,
  status: ProgressBrief["status"] = "not_started",
  mastery_stage: ProgressBrief["mastery_stage"] = 0,
): LessonSummary => ({
  slug,
  title: slug[0]!.toUpperCase() + slug.slice(1),
  description: "",
  topic: { slug: topic, title: topic[0]!.toUpperCase() + topic.slice(1) },
  estimated_minutes: 5,
  evidence_status: "established",
  position: 1,
  progress: {
    status,
    mastery_stage,
    completed_at: null,
    next_review_on: null,
    in_progress_attempt_id: status === "started" ? "attempt-1" : null,
  },
});

const lessons = [
  lesson("anchoring", "judgment", "understood", 3),
  lesson("availability", "judgment", "started"),
  lesson("framing", "decisions"),
];

function discover(overrides: Partial<DiscoverOut> = {}): DiscoverOut {
  return {
    local_date: "2026-11-02",
    primary_action: { type: "continue_lesson", lesson: lessons[1] },
    todays_lesson: lessons[2]!,
    recommended: [],
    progress: { lessons_total: 3, completed: 1, understood: 1 },
    streak: { current: 3, longest: 5, freezes_available: 1, done_today: false, at_risk: true },
    xp: { today: 15, goal: 20, total: 140 },
    reviews_due: 0,
    ...overrides,
  };
}

describe("path helpers", () => {
  test("the server's lesson action places the marker, then today's lesson, then order", () => {
    expect(currentSlug(lessons, discover())).toBe("availability");
    const reviewFirst = discover({ primary_action: { type: "review" } });
    expect(currentSlug(lessons, reviewFirst)).toBe("framing");
    expect(
      currentSlug(lessons, discover({ primary_action: { type: "review" }, todays_lesson: null })),
    ).toBe("availability");
    expect(currentSlug(lessons, undefined)).toBe("availability");
    expect(currentSlug([lessons[0]!], undefined)).toBeNull();
  });

  test("units follow topics in curated order with node states", () => {
    const units = buildPath(lessons, "availability");
    expect(units.map((u) => [u.slug, u.index, u.completed, u.nodes.length])).toEqual([
      ["judgment", 0, 1, 2],
      ["decisions", 1, 0, 1],
    ]);
    expect(units[0]!.nodes.map((n) => n.state)).toEqual(["done", "current"]);
    expect(units[1]!.nodes.map((n) => n.state)).toEqual(["upcoming"]);
  });

  test("node icons and zigzag", () => {
    const [judgment, decisions] = buildPath(lessons, "availability");
    expect(judgment!.nodes.map(nodeIcon)).toEqual(["trophy", "play"]);
    expect(decisions!.nodes.map(nodeIcon)).toEqual(["book"]);
    expect([0, 1, 2, 3, 4].map((n) => nodeOffset(n, 10))).toEqual([0, 10, 0, -10, 0]);
  });

  test("streak labels are supportive", () => {
    expect(streakA11yLabel(discover())).toBe("3-day streak, learn today to keep it");
    const none = discover({
      streak: { current: 0, longest: 2, freezes_available: 1, done_today: false, at_risk: false },
    });
    expect(streakA11yLabel(none)).toBe(strings.discover.noStreak);
  });
});

test("the path shows stats, a recall prompt and tappable lesson nodes", async () => {
  const onOpenLesson = jest.fn();
  const onStartReview = jest.fn();
  await render(
    <ThemeProvider>
      <PathView
        units={buildPath(lessons, "availability")}
        discover={discover({ reviews_due: 2 })}
        onOpenLesson={onOpenLesson}
        onStartReview={onStartReview}
      />
    </ThemeProvider>,
  );
  expect(screen.getByLabelText("3-day streak, learn today to keep it")).toBeOnTheScreen();
  expect(screen.getByLabelText("15/20 XP today")).toBeOnTheScreen();
  expect(screen.getByText(strings.path.reviewTitle)).toBeOnTheScreen();
  expect(screen.getByText(strings.path.continue.toUpperCase())).toBeOnTheScreen();
  expect(screen.getByLabelText(/^Unit 1: Judgment\. 1 of 2 lessons/)).toBeOnTheScreen();

  await fireEvent.press(screen.getByRole("button", { name: "Availability, up next" }));
  expect(onOpenLesson).toHaveBeenCalledWith("availability");
  await fireEvent.press(screen.getByRole("button", { name: "Framing, not started yet" }));
  expect(onOpenLesson).toHaveBeenLastCalledWith("framing");

  await fireEvent.press(screen.getByRole("button", { name: strings.path.reviewCta }));
  await fireEvent.press(screen.getByRole("button", { name: strings.path.dueChip(2) }));
  expect(onStartReview).toHaveBeenCalledTimes(2);
});
