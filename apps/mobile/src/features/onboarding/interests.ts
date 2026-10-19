/**
 * Onboarding interest cards -> topic slugs (docs/spec/02 §2.4, 03 §3.6).
 * Interests only change lesson ordering. One topic per card keeps the
 * selection within the API's limit of 3 topics.
 */

export type InterestKey = "thinking" | "decisions" | "people";

export const INTEREST_CARDS: readonly { key: InterestKey; topic: string }[] = [
  { key: "thinking", topic: "judgment" },
  { key: "decisions", topic: "decisions" },
  { key: "people", topic: "social" },
];

/** Topic slugs for the selected cards, keeping only topics the server publishes. */
export function topicsForSelection(
  selected: ReadonlySet<InterestKey>,
  publishedTopics: ReadonlySet<string>,
): string[] {
  return INTEREST_CARDS.filter((c) => selected.has(c.key) && publishedTopics.has(c.topic)).map(
    (c) => c.topic,
  );
}

export const DAILY_GOALS = [20, 40, 60] as const;
export type DailyGoal = (typeof DAILY_GOALS)[number];
