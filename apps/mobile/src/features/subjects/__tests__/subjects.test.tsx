import { fireEvent, render, screen } from "@testing-library/react-native";

import type { LessonSummary } from "@/api/types";
import { SubjectGrid } from "@/features/subjects/SubjectGrid";
import {
  activeSubject,
  isComingSoon,
  lessonsOf,
  type Subject,
  subjectLook,
} from "@/features/subjects/subjects";
import { strings } from "@/i18n/en";
import { ThemeProvider } from "@/ui/theme";
import { unitColor } from "@/ui/tokens";

const subject = (slug: string, title: string, lessons: number): Subject => ({
  slug,
  title,
  description: `${title} description`,
  topics: [{ slug: `${slug}-t`, title: "T", description: "", position: 1, lesson_count: lessons }],
});

const subjects = [
  subject("psychology", "Psychology", 3),
  subject("math", "Math", 2),
  subject("politics", "Politics", 0),
];

test("the stored subject wins while it has lessons", () => {
  expect(activeSubject(subjects, "math")?.slug).toBe("math");
  expect(activeSubject(subjects, null)?.slug).toBe("psychology");
  expect(activeSubject(subjects, "politics")?.slug).toBe("psychology");
  expect(activeSubject(subjects, "gone")?.slug).toBe("psychology");
  expect(activeSubject([], "math")).toBeNull();
  expect(isComingSoon(subjects[2]!)).toBe(true);
});

test("lessons are filtered by subject and subjects get a stable look", () => {
  const lesson = (slug: string, subjectSlug: string) =>
    ({ slug, subject: { slug: subjectSlug, title: subjectSlug } }) as LessonSummary;
  const all = [lesson("a", "math"), lesson("b", "psychology")];
  expect(lessonsOf(all, "math").map((l) => l.slug)).toEqual(["a"]);
  expect(lessonsOf(all, null)).toHaveLength(2);
  expect(subjectLook("science", 7)).toMatchObject({ color: unitColor(1), icon: "flask" });
  expect(subjectLook("science", 7).decor).toHaveLength(4);
  expect(subjectLook("history", 5).icon).toBe("library");
});

test("the grid selects open subjects and shows the rest as coming soon", async () => {
  const onSelect = jest.fn();
  await render(
    <ThemeProvider>
      <SubjectGrid subjects={subjects} selected="psychology" onSelect={onSelect} />
    </ThemeProvider>,
  );
  expect(screen.getByRole("radio", { name: /^Psychology\./ })).toBeChecked();
  await fireEvent.press(screen.getByRole("radio", { name: /^Math\./ }));
  expect(onSelect).toHaveBeenCalledWith("math");
  expect(screen.getByLabelText(`Politics, ${strings.subjects.soonLabel}`)).toBeOnTheScreen();
  expect(screen.queryByRole("radio", { name: /^Politics/ })).toBeNull();
});
