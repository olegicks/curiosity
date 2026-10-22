/** Profile helpers (docs/spec/02 §2.12). */
import type { ProgressOut } from "@/api/types";
import { stageName } from "@/features/reviews/recall";
import { strings } from "@/i18n/en";

/** Concept counts per mastery stage 1-4, in order. */
export function stageCounts(
  progress: ProgressOut,
): { stage: number; label: string; count: number }[] {
  return [1, 2, 3, 4].map((stage) => ({
    stage,
    label: stageName(stage),
    count: progress.lessons.by_stage[String(stage)] ?? 0,
  }));
}

export function accuracyLabel(progress: ProgressOut): string {
  const { correct, total } = progress.recall_accuracy;
  return total === 0 ? strings.profile.noAccuracy : strings.profile.accuracy(correct, total);
}

export function earnedDate(iso: string): string {
  const date = new Date(iso);
  const months = [
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
  ];
  return `${date.getDate()} ${months[date.getMonth()]!} ${date.getFullYear()}`;
}
