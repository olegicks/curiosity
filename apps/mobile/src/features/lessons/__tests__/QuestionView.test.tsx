import { fireEvent, render, screen } from "@testing-library/react-native";
import { useState } from "react";

import { ApiError, NETWORK_ERROR } from "@/api/errors";
import type { AnswerResult, LessonContent, QuestionOut, Step } from "@/api/types";
import { QuestionView } from "@/features/lessons/QuestionView";
import { StepView } from "@/features/lessons/StepView";
import { strings } from "@/i18n/en";
import { ThemeProvider } from "@/ui/theme";

const question: QuestionOut = {
  id: "q1",
  type: "single_choice",
  prompt: "Which test avoids confirmation bias?",
  options: [
    { id: "a", text: "Read happy reviews" },
    { id: "b", text: "Compare nights with and without" },
  ],
};

const graded = (selected: string): AnswerResult => ({
  question_id: "q1",
  is_correct: selected === "b",
  selected_option_ids: [selected],
  correct_option_ids: ["b"],
  option_feedback: [
    { option_id: "a", is_correct: false, feedback: "Those only fit the belief." },
    { option_id: "b", is_correct: true, feedback: "Both conditions can show you're wrong." },
  ],
  explanation: "Look for evidence that could prove you wrong.",
});

/** Mirrors the player: the result comes back from the server and is passed down. */
function Harness({ submit }: { submit: (ids: string[]) => Promise<AnswerResult> }) {
  const [result, setResult] = useState<AnswerResult>();
  return (
    <ThemeProvider>
      <QuestionView
        question={question}
        result={result}
        onSubmit={async (ids) => {
          const r = await submit(ids);
          setResult(r);
          return r;
        }}
      />
    </ThemeProvider>
  );
}

const option = (text: string) => screen.getByRole("radio", { name: new RegExp(text) });

test("check is disabled until an option is chosen, then the server's verdict is shown", async () => {
  const submit = jest.fn(async (ids: string[]) => graded(ids[0]!));
  await render(<Harness submit={submit} />);

  const check = screen.getByRole("button", { name: strings.lessons.check });
  expect(check).toBeDisabled();

  await fireEvent.press(option("Read happy reviews"));
  expect(option("Read happy reviews")).toBeChecked();
  await fireEvent.press(check);

  expect(submit).toHaveBeenCalledWith(["a"]);
  expect(screen.getByText(strings.lessons.notQuite)).toBeOnTheScreen();
  expect(screen.getByText("Those only fit the belief.")).toBeOnTheScreen();
  expect(screen.getByText("Look for evidence that could prove you wrong.")).toBeOnTheScreen();
  expect(screen.getByText(strings.lessons.correctAnswer)).toBeOnTheScreen();
  expect(screen.queryByRole("button", { name: strings.lessons.check })).toBeNull();
  // answered: options are locked
  expect(option("Compare nights")).toBeDisabled();
});

test("a correct answer is announced as correct", async () => {
  await render(<Harness submit={async (ids) => graded(ids[0]!)} />);
  await fireEvent.press(option("Compare nights"));
  await fireEvent.press(screen.getByRole("button", { name: strings.lessons.check }));
  expect(screen.getByText(strings.lessons.correct)).toBeOnTheScreen();
});

test("a failed request unlocks the options and explains the error", async () => {
  const submit = jest.fn(async () => {
    throw new ApiError(0, NETWORK_ERROR, "offline");
  });
  await render(<Harness submit={submit} />);
  await fireEvent.press(option("Compare nights"));
  await fireEvent.press(screen.getByRole("button", { name: strings.lessons.check }));
  expect(screen.getByText(strings.errors.offline)).toBeOnTheScreen();
  expect(option("Read happy reviews")).not.toBeDisabled();
  expect(screen.getByRole("button", { name: strings.lessons.check })).toBeEnabled();
});

test("every content step type renders", async () => {
  const content = {
    sources: [{ key: "src", citation: "Author (2000). A study.", url: null, doi: null }],
  } as unknown as LessonContent;
  const stepsToRender: Exclude<Step, { type: "question" }>[] = [
    { type: "hook", body: "Ever wondered?", image: null },
    { type: "explanation", title: "The idea", body: "It is **important**.", image: null },
    { type: "example", kind: "research", title: null, body: "In a study…", source_key: "src" },
    { type: "misconception", myth: "Only others are biased.", correction: "Everyone is." },
    { type: "evidence", status: "debated", body: "Researchers disagree.", source_keys: ["src"] },
    { type: "summary", points: ["First point", "Second point"] },
  ];
  await render(
    <ThemeProvider>
      {stepsToRender.map((step) => (
        <StepView key={step.type} step={step} content={content} />
      ))}
    </ThemeProvider>,
  );
  expect(screen.getByText("Ever wondered?")).toBeOnTheScreen();
  expect(screen.getByText("important")).toBeOnTheScreen();
  expect(screen.getByText("Author (2000). A study.")).toBeOnTheScreen();
  expect(screen.getByText("Only others are biased.")).toBeOnTheScreen();
  expect(screen.getByText(new RegExp(strings.lessons.debated))).toBeOnTheScreen();
  expect(screen.getByText("Second point")).toBeOnTheScreen();
});
