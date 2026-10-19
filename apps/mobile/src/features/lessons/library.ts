/** Learn library grouping and status helpers (docs/spec/02 §2.6). */
import type { LessonSummary, ProgressBrief } from "@/api/types";
import { strings } from "@/i18n/en";

export type LibraryFilter = "all" | "not_started" | "in_progress" | "completed";

export type TopicGroup = { slug: string; title: string; lessons: LessonSummary[] };

export function progressBucket(progress: ProgressBrief): Exclude<LibraryFilter, "all"> {
  if (progress.status === "not_started") return "not_started";
  if (progress.status === "started") return "in_progress";
  return "completed";
}

/** Lessons arrive in curated order; keep it, grouped by topic. */
export function groupByTopic(lessons: LessonSummary[], filter: LibraryFilter): TopicGroup[] {
  const groups: TopicGroup[] = [];
  for (const lesson of lessons) {
    if (filter !== "all" && progressBucket(lesson.progress) !== filter) continue;
    let group = groups.find((g) => g.slug === lesson.topic.slug);
    if (!group) {
      group = { slug: lesson.topic.slug, title: lesson.topic.title, lessons: [] };
      groups.push(group);
    }
    group.lessons.push(lesson);
  }
  return groups;
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
