/** Lesson status helpers shared by the path, intro and rows. */
import type { ProgressBrief } from "@/api/types";
import { strings } from "@/i18n/en";

export type LibraryFilter = "all" | "not_started" | "in_progress" | "completed";

export function progressBucket(progress: ProgressBrief): Exclude<LibraryFilter, "all"> {
  if (progress.status === "not_started") return "not_started";
  if (progress.status === "started") return "in_progress";
  return "completed";
}

export function statusLabel(progress: ProgressBrief): string {
  return strings.lessons.status[progress.status];
}

export function startLabel(progress: ProgressBrief): string {
  if (progress.in_progress_attempt_id) return strings.lessons.continue;
  return progress.status === "not_started" ? strings.lessons.start : strings.lessons.revisit;
}

export function xpLabel(reason: string): string {
  const labels: Record<string, string> = strings.lessons.xpReasons;
  return labels[reason] ?? reason;
}
