/** Recall helpers (docs/spec/02 §2.10-2.11). Pure; scheduling itself is server-side. */
import type { ReviewAnswerResult, ReviewItem } from "@/api/types";
import { strings } from "@/i18n/en";

const SESSION_MAX_ITEMS = 20;
const WEEKDAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** Parse a YYYY-MM-DD local date without timezone shifts. */
function parseDay(value: string): Date {
  const [y, m, d] = value.split("-").map(Number) as [number, number, number];
  return new Date(y, m - 1, d);
}

export function toDay(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

export function daysBetween(from: string, to: string): number {
  return Math.round((parseDay(to).getTime() - parseDay(from).getTime()) / 86_400_000);
}

/** "today", "tomorrow", a weekday within the next week, else "Mon 23 Nov". */
export function friendlyDay(day: string, today: string): string {
  const diff = daysBetween(today, day);
  if (diff <= 0) return strings.recall.today;
  if (diff === 1) return strings.recall.tomorrow;
  const date = parseDay(day);
  if (diff < 7) return WEEKDAYS[date.getDay()]!;
  return `${WEEKDAYS[date.getDay()]!.slice(0, 3)} ${date.getDate()} ${MONTHS[date.getMonth()]!}`;
}

export function dueLabel(dueOn: string, today: string): string {
  const diff = daysBetween(today, dueOn);
  if (diff <= 0) return strings.recall.dueToday;
  if (diff === 1) return strings.recall.dueTomorrow;
  return strings.recall.dueIn(diff);
}

/** Sessions hold at most 20 items, so larger backlogs read "20+". */
export function dueCountLabel(count: number): string {
  return count > SESSION_MAX_ITEMS ? `${SESSION_MAX_ITEMS}+` : String(count);
}

export function scheduleMessage(result: ReviewAnswerResult): string {
  if (!result.is_correct) return strings.recall.backTomorrow;
  return strings.recall.seeYouIn(result.schedule.next_interval_days);
}

export function stageName(stage: number): string {
  return strings.recall.stages[stage as 0 | 1 | 2 | 3 | 4] ?? "";
}

/** Resume at the first unanswered item (answers are stored server-side). */
export function firstOpenItem(items: ReviewItem[]): number {
  const index = items.findIndex((item) => item.result === null || item.result === undefined);
  return index === -1 ? items.length : index;
}
