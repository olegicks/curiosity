/** Reward screen helpers (D-17). Display only: XP and streaks come from the server. */

export type WeekDay = { label: string; done: boolean; today: boolean };

const LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

/**
 * Monday-to-Sunday strip for the week containing `today`. A streak of n days covers
 * today and the n-1 days before it, so those are marked done.
 */
export function weekStrip(today: Date, streak: number): WeekDay[] {
  const weekday = (today.getDay() + 6) % 7; // Monday = 0
  return LABELS.map((label, i) => {
    const daysAgo = weekday - i;
    return { label, today: daysAgo === 0, done: daysAgo >= 0 && daysAgo < streak };
  });
}
