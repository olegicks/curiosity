import { fireEvent, render, screen } from "@testing-library/react-native";
import { useState } from "react";

import type { AnswerResult, QuestionOut } from "@/api/types";
import {
  a11yStep,
  formatNumber,
  fraction,
  snap,
  startValue,
  valueAt,
  withUnit,
} from "@/features/lessons/estimate";
import { EstimateView } from "@/features/lessons/EstimateView";
import { weekStrip } from "@/features/lessons/reward";
import { strings } from "@/i18n/en";
import { ThemeProvider } from "@/ui/theme";

const config = { min: 0, max: 8000, step: 100 };

test("slider maths snaps to the grid and stays in range", () => {
  expect(snap(3749, config)).toBe(3700);
  expect(snap(-50, config)).toBe(0);
  expect(snap(9000, config)).toBe(8000);
  expect(snap(0.26, { min: 0, max: 1, step: 0.05 })).toBe(0.25);
  expect(fraction(2000, config)).toBe(0.25);
  expect(valueAt(150, 300, config)).toBe(4000);
  expect(valueAt(10, 0, config)).toBe(0);
  expect(a11yStep(config)).toBe(400);
  expect(a11yStep({ min: 2, max: 200, step: 1 })).toBe(10);
  expect(startValue(config)).toBe(4000);
  expect(formatNumber(3700)).toBe("3,700");
  expect(formatNumber(1234567.5)).toBe("1,234,567.5");
  expect(formatNumber(-2500)).toBe("-2,500");
  expect(withUnit(3700, "km")).toBe("3,700 km");
  expect(withUnit(93, "%")).toBe("93%");
});

test("week strip marks the streak days up to today", () => {
  const thursday = new Date(2026, 9, 22); // 22 Oct 2026 is a Thursday
  const strip = weekStrip(thursday, 3);
  expect(strip.map((d) => d.done)).toEqual([false, true, true, true, false, false, false]);
  expect(strip.find((d) => d.today)?.label).toBe("Thu");
  expect(weekStrip(thursday, 0).some((d) => d.done)).toBe(false);
});

const question: QuestionOut = {
  id: "q-est",
  type: "estimate",
  prompt: "How long is the Mississippi?",
  options: [],
  estimate: { min: 0, max: 8000, step: 100, unit: "km", anchor: 7000 },
};

function Harness({ submit }: { submit: (value: number) => Promise<AnswerResult> }) {
  const [result, setResult] = useState<AnswerResult>();
  return (
    <ThemeProvider>
      <EstimateView
        question={question}
        result={result}
        onSubmit={async (value) => {
          const r = await submit(value);
          setResult(r);
          return r;
        }}
      />
    </ThemeProvider>
  );
}

test("the learner adjusts the slider, then the server's verdict reveals the real value", async () => {
  const submit = jest.fn(async (value: number): Promise<AnswerResult> => ({
    question_id: "q-est",
    is_correct: false,
    selected_option_ids: [],
    correct_option_ids: [],
    option_feedback: [],
    explanation: "About 3,700 km.",
    estimate: { value, answer: 3700, tolerance: 600, unit: "km" },
  }));
  await render(<Harness submit={submit} />);

  const check = screen.getByRole("button", { name: strings.lessons.check });
  expect(check).toBeDisabled(); // nothing chosen yet
  expect(screen.getByText(strings.lessons.estimate.anchor("7,000"))).toBeOnTheScreen();

  const slider = screen.getByRole("adjustable");
  await fireEvent(slider, "accessibilityAction", { nativeEvent: { actionName: "increment" } });
  await fireEvent(slider, "accessibilityAction", { nativeEvent: { actionName: "increment" } });
  expect(screen.getByText("4,800 km")).toBeOnTheScreen();

  await fireEvent.press(screen.getByRole("button", { name: strings.lessons.check }));
  expect(submit).toHaveBeenCalledWith(4800);
  expect(await screen.findByText(strings.lessons.estimate.far)).toBeOnTheScreen();
  expect(
    screen.getByText(strings.lessons.estimate.result("4,800 km", "3,700 km")),
  ).toBeOnTheScreen();
  expect(screen.getByText(strings.lessons.estimate.real("3,700"))).toBeOnTheScreen();
});
