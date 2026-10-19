/**
 * Lesson player rules (docs/spec/02 §2.8). Pure: the server grades answers; these
 * helpers only decide what the learner may see and do next.
 */
import type { AnswerResult, QuestionOut, Step } from "@/api/types";
import type { OptionState } from "@/ui/OptionCard";

export type { OptionState } from "@/ui/OptionCard";

/** Index of the first question step that has no answer yet. */
export function firstUnansweredQuestion(steps: Step[], answered: ReadonlySet<string>): number {
  const index = steps.findIndex((s) => s.type === "question" && !answered.has(s.question_id));
  return index === -1 ? steps.length - 1 : index;
}

/**
 * Where to resume (FR-LRN-3): the saved step index from this device, but never past
 * an unanswered question. Without a saved index, continue after the last answer.
 */
export function resumeIndex(
  steps: Step[],
  answered: ReadonlySet<string>,
  saved: number | null,
): number {
  if (steps.length === 0) return 0;
  const bound = firstUnansweredQuestion(steps, answered);
  let candidate = saved;
  if (candidate === null) {
    let lastAnswered = -1;
    steps.forEach((s, i) => {
      if (s.type === "question" && answered.has(s.question_id)) lastAnswered = i;
    });
    candidate = lastAnswered + 1;
  }
  return Math.max(0, Math.min(candidate, bound, steps.length - 1));
}

/** A question step blocks Continue until it has been answered. */
export function canContinue(step: Step, answers: Readonly<Record<string, AnswerResult>>): boolean {
  return step.type !== "question" || step.question_id in answers;
}

export function isSingleAnswer(question: QuestionOut): boolean {
  return question.type !== "multi_select";
}

export function toggleSelection(
  question: QuestionOut,
  current: string[],
  optionId: string,
): string[] {
  if (isSingleAnswer(question)) return [optionId];
  return current.includes(optionId)
    ? current.filter((id) => id !== optionId)
    : [...current, optionId];
}

export function optionState(
  optionId: string,
  selection: readonly string[],
  result: AnswerResult | undefined,
): OptionState {
  if (!result) return selection.includes(optionId) ? "selected" : "idle";
  const chosen = result.selected_option_ids.includes(optionId);
  const correct = result.correct_option_ids.includes(optionId);
  if (chosen) return correct ? "correct" : "incorrect";
  return correct ? "missed" : "locked";
}

/** Feedback to show for an answer: the chosen options' feedback, then the explanation. */
export function feedbackLines(result: AnswerResult): string[] {
  const chosen = result.option_feedback.filter((f) =>
    result.selected_option_ids.includes(f.option_id),
  );
  return [...chosen.map((f) => f.feedback), result.explanation];
}
