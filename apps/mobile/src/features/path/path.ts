/** The learning path (D-16): one unit per topic, each lesson a node, in curated order. */
import type { DiscoverOut, LessonSummary, ProgressBrief } from "@/api/types";
import { strings } from "@/i18n/en";
import type { IconName } from "@/ui/Icon";

export type NodeState = "done" | "current" | "upcoming";

export type PathNode = { lesson: LessonSummary; state: NodeState; started: boolean };

export type PathUnit = {
  slug: string;
  title: string;
  /** 0-based position in the path; picks the unit colour. */
  index: number;
  nodes: PathNode[];
  completed: number;
};

export function isLearned(progress: ProgressBrief): boolean {
  return progress.status !== "not_started" && progress.status !== "started";
}

/**
 * The lesson the "Start" marker sits on. The server's primary action wins; while a
 * review is due, today's lesson or the first unfinished lesson keeps the marker.
 */
export function currentSlug(
  lessons: LessonSummary[],
  discover: DiscoverOut | undefined,
): string | null {
  const action = discover?.primary_action;
  if (
    action &&
    (action.type === "continue_lesson" || action.type === "start_lesson") &&
    action.lesson
  ) {
    return action.lesson.slug;
  }
  const today = discover?.todays_lesson;
  if (today && !isLearned(today.progress)) return today.slug;
  return lessons.find((l) => !isLearned(l.progress))?.slug ?? null;
}

/** Lessons arrive in curated order; keep it, one unit per topic. */
export function buildPath(lessons: LessonSummary[], current: string | null): PathUnit[] {
  const units: PathUnit[] = [];
  for (const lesson of lessons) {
    let unit = units.find((u) => u.slug === lesson.topic.slug);
    if (!unit) {
      unit = {
        slug: lesson.topic.slug,
        title: lesson.topic.title,
        index: units.length,
        nodes: [],
        completed: 0,
      };
      units.push(unit);
    }
    const learned = isLearned(lesson.progress);
    const state: NodeState = lesson.slug === current ? "current" : learned ? "done" : "upcoming";
    unit.nodes.push({ lesson, state, started: lesson.progress.status === "started" });
    if (learned) unit.completed += 1;
  }
  return units;
}

/** Horizontal offset of the n-th node: a gentle zigzag (0, right, 0, left, …). */
export function nodeOffset(n: number, amplitude: number): number {
  return [0, 1, 0, -1][n % 4]! * amplitude;
}

export function nodeIcon(node: PathNode): IconName {
  if (node.state === "current") return node.started ? "play" : "star";
  if (node.state === "upcoming") return node.started ? "play" : "book";
  return node.lesson.progress.mastery_stage >= 3 ? "trophy" : "checkmark";
}

export function streakA11yLabel(discover: DiscoverOut): string {
  const { current, done_today, at_risk } = discover.streak;
  if (current === 0) return strings.discover.noStreak;
  const base = strings.path.streak(current);
  if (done_today) return `${base}, ${strings.discover.doneToday}`;
  return at_risk ? `${base}, ${strings.discover.atRisk}` : base;
}
