import type { AnswerResult, LessonSummary, ProgressBrief, QuestionOut, Step } from "@/api/types";
import { groupByTopic, progressBucket, startLabel, xpLabel } from "@/features/lessons/library";
import {
  canContinue,
  feedbackLines,
  optionState,
  resumeIndex,
  toggleSelection,
} from "@/features/lessons/player";
import { strings } from "@/i18n/en";
import { parseInline, parseMarkdown } from "@/ui/markdownParser";

const steps: Step[] = [
  { type: "hook", body: "Hook?", image: null },
  { type: "explanation", title: null, body: "Idea", image: null },
  { type: "question", question_id: "q1" },
  { type: "example", kind: "illustrative", title: null, body: "Imagine", source_key: null },
  { type: "question", question_id: "q2" },
  { type: "summary", points: ["One", "Two"] },
];

const result = (selected: string[], correct: string[]): AnswerResult => ({
  question_id: "q1",
  is_correct: selected.length === correct.length && selected.every((s) => correct.includes(s)),
  selected_option_ids: selected,
  correct_option_ids: correct,
  option_feedback: ["a", "b", "c"].map((id) => ({
    option_id: id,
    is_correct: correct.includes(id),
    feedback: `feedback ${id}`,
  })),
  explanation: "Because.",
});

describe("markdown", () => {
  test("parses bold and italic inline runs", () => {
    expect(parseInline("A **bold** and *quiet* idea")).toEqual([
      { text: "A " },
      { text: "bold", bold: true },
      { text: " and " },
      { text: "quiet", italic: true },
      { text: " idea" },
    ]);
  });

  test("splits paragraphs and bullet lists, joining wrapped lines", () => {
    const blocks = parseMarkdown("First line\nwraps here.\n\n- one\n- **two**\n\nLast.");
    expect(blocks).toEqual([
      { kind: "paragraph", inlines: [{ text: "First line wraps here." }] },
      { kind: "list", items: [[{ text: "one" }], [{ text: "two", bold: true }]] },
      { kind: "paragraph", inlines: [{ text: "Last." }] },
    ]);
  });

  test("a line starting with italic text is not a bullet", () => {
    expect(parseMarkdown("*which* evidence")[0]?.kind).toBe("paragraph");
  });
});

describe("player", () => {
  test("resume never skips an unanswered question", () => {
    expect(resumeIndex(steps, new Set(), null)).toBe(0);
    expect(resumeIndex(steps, new Set(), 4)).toBe(2); // bounded by q1
    expect(resumeIndex(steps, new Set(["q1"]), null)).toBe(3); // after the last answer
    expect(resumeIndex(steps, new Set(["q1"]), 1)).toBe(1); // saved earlier position wins
    expect(resumeIndex(steps, new Set(["q1", "q2"]), 99)).toBe(5);
  });

  test("questions block Continue until answered", () => {
    expect(canContinue(steps[0]!, {})).toBe(true);
    expect(canContinue(steps[2]!, {})).toBe(false);
    expect(canContinue(steps[2]!, { q1: result(["a"], ["a"]) })).toBe(true);
  });

  test("selection is single or multiple by question type", () => {
    const single = { type: "single_choice" } as QuestionOut;
    const multi = { type: "multi_select" } as QuestionOut;
    expect(toggleSelection(single, ["a"], "b")).toEqual(["b"]);
    expect(toggleSelection(multi, ["a"], "b")).toEqual(["a", "b"]);
    expect(toggleSelection(multi, ["a", "b"], "a")).toEqual(["b"]);
  });

  test("option states before and after the server's result", () => {
    expect(optionState("a", ["a"], undefined)).toBe("selected");
    expect(optionState("b", ["a"], undefined)).toBe("idle");
    const wrong = result(["a"], ["b"]);
    expect(optionState("a", [], wrong)).toBe("incorrect");
    expect(optionState("b", [], wrong)).toBe("missed");
    expect(optionState("c", [], wrong)).toBe("locked");
    expect(optionState("b", [], result(["b"], ["b"]))).toBe("correct");
  });

  test("feedback shows the chosen options' feedback, then the explanation", () => {
    expect(feedbackLines(result(["a", "c"], ["a"]))).toEqual([
      "feedback a",
      "feedback c",
      "Because.",
    ]);
  });
});

describe("library", () => {
  const progress = (status: ProgressBrief["status"], attempt: string | null = null) =>
    ({
      status,
      mastery_stage: 0,
      completed_at: null,
      next_review_on: null,
      in_progress_attempt_id: attempt,
    }) as ProgressBrief;
  const lesson = (slug: string, topic: string, status: ProgressBrief["status"]) =>
    ({
      slug,
      title: slug,
      description: "",
      topic: { slug: topic, title: topic.toUpperCase() },
      estimated_minutes: 5,
      evidence_status: "established",
      position: 1,
      progress: progress(status),
    }) as LessonSummary;

  const lessons = [
    lesson("a", "judgment", "not_started"),
    lesson("b", "decisions", "started"),
    lesson("c", "judgment", "understood"),
  ];

  test("groups by topic in curated order and filters by progress", () => {
    expect(groupByTopic(lessons, "all").map((g) => [g.slug, g.lessons.map((l) => l.slug)])).toEqual(
      [
        ["judgment", ["a", "c"]],
        ["decisions", ["b"]],
      ],
    );
    expect(groupByTopic(lessons, "completed").map((g) => g.lessons[0]?.slug)).toEqual(["c"]);
    expect(groupByTopic(lessons, "in_progress").map((g) => g.slug)).toEqual(["decisions"]);
    expect(progressBucket(progress("retained"))).toBe("completed");
  });

  test("start button wording", () => {
    expect(startLabel(progress("not_started"))).toBe(strings.lessons.start);
    expect(startLabel(progress("started", "attempt-1"))).toBe(strings.lessons.continue);
    expect(startLabel(progress("recalled"))).toBe(strings.lessons.revisit);
    expect(startLabel(progress("recalled", "attempt-2"))).toBe(strings.lessons.continue);
  });

  test("XP reasons have labels", () => {
    expect(xpLabel("lesson_perfect")).toBe("Perfect first try");
    expect(xpLabel("something_new")).toBe("something_new");
  });
});
