/** Discover helpers (docs/spec/02 §2.5). The server decides the primary action. */
import type { DiscoverOut } from "@/api/types";
import { friendlyDay } from "@/features/reviews/recall";
import { strings } from "@/i18n/en";

export type Destination =
  | { kind: "review" }
  | { kind: "lesson"; slug: string }
  | { kind: "play"; slug: string }
  | { kind: "learn" };

export type PrimaryCard = {
  eyebrow: string;
  title: string;
  body: string | null;
  cta: string;
  destination: Destination;
};

export function greeting(hour: number, name: string | null): string {
  const base =
    hour < 5 || hour >= 18
      ? strings.discover.evening
      : hour < 12
        ? strings.discover.morning
        : strings.discover.afternoon;
  return name ? `${base}, ${name}` : base;
}

/** Copy and navigation for the primary action card. */
export function primaryCard(discover: DiscoverOut, today: string): PrimaryCard {
  const action = discover.primary_action;
  switch (action.type) {
    case "review": {
      const due = action.review?.due_count ?? discover.reviews_due;
      return {
        eyebrow: strings.discover.reviewsDue,
        title: strings.discover.reviewTitle(due, action.review?.estimated_minutes ?? 1),
        body: strings.discover.reviewBody,
        cta: action.review?.open_session_id ? strings.recall.resume : strings.discover.reviewCta,
        destination: { kind: "review" },
      };
    }
    case "continue_lesson":
      return {
        eyebrow: strings.discover.continueEyebrow,
        title: action.lesson?.title ?? "",
        body: action.lesson?.description ?? null,
        cta: strings.lessons.continue,
        destination: { kind: "play", slug: action.lesson?.slug ?? "" },
      };
    case "start_lesson":
      return {
        eyebrow: strings.discover.todaysLesson,
        title: action.lesson?.title ?? "",
        body: action.lesson?.description ?? null,
        cta: strings.lessons.start,
        destination: { kind: "lesson", slug: action.lesson?.slug ?? "" },
      };
    case "caught_up":
      return {
        eyebrow: strings.discover.caughtUpEyebrow,
        title: strings.discover.caughtUp,
        body: action.next_review_on
          ? strings.discover.nextReview(friendlyDay(action.next_review_on, today))
          : null,
        cta: strings.discover.revisitLesson,
        destination: { kind: "learn" },
      };
  }
}

/** Show the separate "Today's lesson" card unless the primary card already is it. */
export function showTodaysLessonCard(discover: DiscoverOut): boolean {
  if (!discover.todays_lesson) return false;
  const action = discover.primary_action;
  return !(action.type === "start_lesson" && action.lesson?.slug === discover.todays_lesson.slug);
}

export function streakA11yLabel(discover: DiscoverOut): string {
  const { current, done_today, at_risk } = discover.streak;
  if (current === 0) return strings.discover.noStreak;
  const base = strings.recall.streak(current);
  if (done_today) return `${base}, ${strings.discover.doneToday}`;
  return at_risk ? `${base}, ${strings.discover.atRisk}` : base;
}
