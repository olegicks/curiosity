import { fireEvent, render, screen } from "@testing-library/react-native";
import { useState } from "react";

import type { ReviewAnswerResult, ReviewItem, ReviewSessionSummary } from "@/api/types";
import {
  daysBetween,
  dueCountLabel,
  dueLabel,
  firstOpenItem,
  friendlyDay,
  scheduleMessage,
  stageName,
  toDay,
} from "@/features/reviews/recall";
import { ReviewItemView } from "@/features/reviews/ReviewItemView";
import { SessionSummaryView } from "@/features/reviews/SessionSummaryView";
import { strings } from "@/i18n/en";
import { ThemeProvider } from "@/ui/theme";

const item: ReviewItem = {
  id: "item-1",
  position: 1,
  lesson: { slug: "anchoring", title: "Anchoring" },
  question: {
    id: "q9",
    type: "single_choice",
    prompt: "A store shows a high 'original' price first. What is at work?",
    options: [
      { id: "a", text: "Anchoring" },
      { id: "b", text: "Availability" },
    ],
  },
  result: null,
};

const graded = (correct: boolean, interval: number, before: number, after: number) =>
  ({
    is_correct: correct,
    quality: correct ? 4 : 1,
    selected_option_ids: [correct ? "a" : "b"],
    correct_option_ids: ["a"],
    option_feedback: [
      { option_id: "a", is_correct: true, feedback: "The first number pulls the estimate." },
      { option_id: "b", is_correct: false, feedback: "Nothing here is about ease of recall." },
    ],
    explanation: "An initial value biases later judgments.",
    schedule: {
      previous_interval_days: 1,
      next_interval_days: interval,
      next_due_on: "2026-11-09",
    },
    mastery_stage: { before, after },
  }) as ReviewAnswerResult;

describe("recall helpers", () => {
  test("day arithmetic works across months and years", () => {
    expect(daysBetween("2026-12-30", "2027-01-02")).toBe(3);
    expect(toDay(new Date(2026, 10, 2))).toBe("2026-11-02");
  });

  test("friendly day names", () => {
    const today = "2026-11-02"; // a Monday
    expect(friendlyDay("2026-11-02", today)).toBe("today");
    expect(friendlyDay("2026-11-03", today)).toBe("tomorrow");
    expect(friendlyDay("2026-11-05", today)).toBe("Thursday");
    expect(friendlyDay("2026-11-23", today)).toBe("Mon 23 Nov");
  });

  test("due labels and counts", () => {
    expect(dueLabel("2026-11-01", "2026-11-02")).toBe(strings.recall.dueToday);
    expect(dueLabel("2026-11-03", "2026-11-02")).toBe(strings.recall.dueTomorrow);
    expect(dueLabel("2026-11-08", "2026-11-02")).toBe("In 6 days");
    expect(dueCountLabel(5)).toBe("5");
    expect(dueCountLabel(23)).toBe("20+");
  });

  test("scheduling feedback", () => {
    expect(scheduleMessage(graded(true, 6, 1, 2))).toBe("See you again in 6 days.");
    expect(scheduleMessage(graded(false, 1, 3, 1))).toBe(strings.recall.backTomorrow);
    expect(stageName(3)).toBe("Understood");
  });

  test("sessions resume at the first unanswered item", () => {
    const answered = { ...item, id: "done", result: graded(true, 6, 1, 2) };
    expect(firstOpenItem([answered, item])).toBe(1);
    expect(firstOpenItem([answered])).toBe(1);
  });
});

function Harness({ submit }: { submit: jest.Mock }) {
  const [result, setResult] = useState<ReviewAnswerResult>();
  return (
    <ThemeProvider>
      <ReviewItemView
        item={item}
        result={result}
        onSubmit={async (ids, guessed) => {
          const r = (await submit(ids, guessed)) as ReviewAnswerResult;
          setResult(r);
          return r;
        }}
      />
    </ThemeProvider>
  );
}

test("the guessing toggle is sent with the answer and scheduling is shown", async () => {
  const submit = jest.fn(async () => graded(true, 6, 1, 2));
  await render(<Harness submit={submit} />);
  expect(screen.getByText(strings.recall.concept("Anchoring"))).toBeOnTheScreen();

  await fireEvent(screen.getByLabelText(strings.recall.guessing), "valueChange", true);
  await fireEvent.press(screen.getByRole("radio", { name: /Anchoring/ }));
  await fireEvent.press(screen.getByRole("button", { name: strings.lessons.check }));

  expect(submit).toHaveBeenCalledWith(["a"], true);
  expect(screen.getByText("See you again in 6 days.")).toBeOnTheScreen();
  expect(screen.getByText(strings.recall.now("Recalled"))).toBeOnTheScreen();
  expect(screen.queryByText(strings.recall.revisitLesson)).toBeNull();
});

test("a failed recall comes back tomorrow and offers the lesson", async () => {
  await render(<Harness submit={jest.fn(async () => graded(false, 1, 3, 1))} />);
  await fireEvent.press(screen.getByRole("radio", { name: /Availability/ }));
  await fireEvent.press(screen.getByRole("button", { name: strings.lessons.check }));
  expect(screen.getByText(strings.recall.backTomorrow)).toBeOnTheScreen();
  expect(screen.getByText(strings.recall.now("Learned"))).toBeOnTheScreen();
  expect(screen.getByRole("button", { name: strings.recall.revisitLesson })).toBeOnTheScreen();
});

test("the session summary names what improved and what to revisit", async () => {
  const summary: ReviewSessionSummary = {
    correct: 1,
    total: 2,
    advanced: [{ slug: "anchoring", from: 1, to: 2 }],
    to_revisit: [{ slug: "framing-effect", title: "The framing effect" }],
    xp_total: 16,
  };
  await render(
    <ThemeProvider>
      <SessionSummaryView
        summary={summary}
        completed
        titles={{ anchoring: "Anchoring" }}
        streak={3}
        achievements={[
          {
            code: "first_recall",
            title: "It stuck",
            description: "Recall a concept.",
            earned_at: null,
          },
        ]}
      />
    </ThemeProvider>,
  );
  expect(screen.getByText(strings.recall.summaryTitle)).toBeOnTheScreen();
  expect(screen.getByText("1 of 2 recalled")).toBeOnTheScreen();
  expect(screen.getByText("+16 XP")).toBeOnTheScreen();
  expect(screen.getByText("3-day streak")).toBeOnTheScreen();
  expect(screen.getByText("Anchoring: Learned → Recalled")).toBeOnTheScreen();
  expect(screen.getByRole("button", { name: "The framing effect" })).toBeOnTheScreen();
  expect(screen.getByText("It stuck")).toBeOnTheScreen();
});
