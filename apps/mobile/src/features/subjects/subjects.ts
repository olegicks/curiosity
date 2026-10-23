/** Subjects and their roadmaps (D-17). Colours and icons are client-side presentation. */
import type { LessonSummary, SubjectsOut } from "@/api/types";
import type { IconName } from "@/ui/Icon";
import { type UnitColor, unitColor } from "@/ui/tokens";

export type Subject = SubjectsOut["items"][number];

const LOOKS: Record<string, { color: number; icon: IconName }> = {
  psychology: { color: 0, icon: "bulb" },
  science: { color: 1, icon: "flask" },
  math: { color: 2, icon: "dice" },
  economics: { color: 3, icon: "trending-up" },
};

export function subjectLook(slug: string, index: number): { color: UnitColor; icon: IconName } {
  const look = LOOKS[slug];
  return {
    color: unitColor(look ? look.color : index),
    icon: look ? look.icon : "library",
  };
}

export function lessonCount(subject: Subject): number {
  return subject.topics.reduce((sum, t) => sum + t.lesson_count, 0);
}

/** Published subjects without lessons are shown as "coming soon". */
export function isComingSoon(subject: Subject): boolean {
  return lessonCount(subject) === 0;
}

/** The stored choice if it still has lessons, else the first subject that does. */
export function activeSubject(subjects: Subject[], stored: string | null): Subject | null {
  const open = subjects.filter((s) => !isComingSoon(s));
  return open.find((s) => s.slug === stored) ?? open[0] ?? null;
}

export function lessonsOf(lessons: LessonSummary[], subject: string | null): LessonSummary[] {
  return subject ? lessons.filter((l) => l.subject.slug === subject) : lessons;
}
