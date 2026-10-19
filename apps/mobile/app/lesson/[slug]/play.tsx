import AsyncStorage from "@react-native-async-storage/async-storage";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { router, useLocalSearchParams, usePreventRemove } from "expo-router";
import { type ReactNode, useCallback, useEffect, useState } from "react";
import { Alert, Pressable, ScrollView, StyleSheet, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { errorMessage } from "@/api/errors";
import type { AnswerResult, AttemptResponse, CompletionResponse } from "@/api/types";
import { useAuth } from "@/features/auth/AuthProvider";
import { CompletionView } from "@/features/lessons/CompletionView";
import { canContinue, resumeIndex } from "@/features/lessons/player";
import { QuestionView } from "@/features/lessons/QuestionView";
import { StepView } from "@/features/lessons/StepView";
import { strings } from "@/i18n/en";
import { Banner } from "@/ui/Banner";
import { Button } from "@/ui/Button";
import { ProgressBar } from "@/ui/ProgressBar";
import { ErrorState, LoadingBlocks } from "@/ui/States";
import { Text } from "@/ui/Text";
import { useTheme } from "@/ui/theme";
import { readingMaxWidth, spacing, touchTarget } from "@/ui/tokens";

const stepKey = (attemptId: string) => `attempt-step:${attemptId}`;

/** The step-by-step lesson player (docs/spec/02 §2.8). The server grades every answer. */
export default function LessonPlayerScreen() {
  const { slug } = useLocalSearchParams<{ slug: string }>();
  const { api } = useAuth();

  // Starting is idempotent: an open attempt is resumed, pinned to its lesson version.
  const attempt = useQuery({
    queryKey: ["attempt", slug],
    queryFn: () => api.attempts.start(slug),
    staleTime: Infinity,
    gcTime: 0,
    retry: false,
    refetchOnWindowFocus: false,
  });

  if (attempt.data) return <Player key={attempt.data.attempt.id} data={attempt.data} />;
  return (
    <Frame header={<CloseButton />}>
      {attempt.isError ? (
        <ErrorState message={errorMessage(attempt.error)} onRetry={() => void attempt.refetch()} />
      ) : (
        <LoadingBlocks count={3} />
      )}
    </Frame>
  );
}

function Player({ data }: { data: AttemptResponse }) {
  const { api } = useAuth();
  const queryClient = useQueryClient();
  const steps = data.content.steps;
  const attemptId = data.attempt.id;

  const [answers, setAnswers] = useState<Record<string, AnswerResult>>(() =>
    Object.fromEntries(data.attempt.answers.map((a) => [a.question_id, a])),
  );
  const [index, setIndex] = useState<number | null>(null);
  const [completion, setCompletion] = useState<CompletionResponse | null>(null);
  const [completing, setCompleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Resume: the step index saved on this device, bounded by the answered questions.
  useEffect(() => {
    let active = true;
    AsyncStorage.getItem(stepKey(attemptId))
      .catch(() => null)
      .then((raw) => {
        if (!active) return;
        const saved = raw == null ? null : Number(raw);
        const answered = new Set(data.attempt.answers.map((a) => a.question_id));
        setIndex(resumeIndex(steps, answered, Number.isFinite(saved) ? saved : null));
      });
    return () => {
      active = false;
    };
  }, [attemptId, data.attempt.answers, steps]);

  useEffect(() => {
    if (index !== null) AsyncStorage.setItem(stepKey(attemptId), String(index)).catch(() => {});
  }, [attemptId, index]);

  // Leaving mid-lesson asks first (close button, gestures and the Android back button).
  const [leaving, setLeaving] = useState(false);
  usePreventRemove(completion === null && !leaving, ({ repeat }) => {
    Alert.alert(strings.lessons.leaveTitle, strings.lessons.leaveBody, [
      { text: strings.lessons.stay, style: "cancel" },
      {
        text: strings.lessons.leave,
        style: "destructive",
        onPress: () => {
          setLeaving(true);
          repeat();
        },
      },
    ]);
  });

  const submit = useCallback(
    async (questionId: string, optionIds: string[]) => {
      const result = await api.attempts.answer(attemptId, questionId, optionIds);
      setAnswers((current) => ({ ...current, [questionId]: result }));
      return result;
    },
    [api, attemptId],
  );

  const complete = async () => {
    setCompleting(true);
    setError(null);
    try {
      setCompletion(await api.attempts.complete(attemptId));
      AsyncStorage.removeItem(stepKey(attemptId)).catch(() => {});
      for (const key of ["lessons", "lesson", "discover"]) {
        void queryClient.invalidateQueries({ queryKey: [key] });
      }
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setCompleting(false);
    }
  };

  const step = index === null ? undefined : steps[index];
  const last = index === steps.length - 1;
  const next = completion?.next_lesson ?? null;

  const header = (
    <>
      <CloseButton />
      {index !== null && !completion ? (
        <ProgressBar
          value={index + 1}
          max={steps.length}
          label={strings.lessons.step(index + 1, steps.length)}
        />
      ) : (
        <View style={styles.flex} />
      )}
      {index !== null && index > 0 && !completion ? (
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={strings.lessons.back}
          onPress={() => setIndex(Math.max(index - 1, 0))}
          style={styles.iconButton}
        >
          <Text variant="label" tone="accent">
            {strings.lessons.back}
          </Text>
        </Pressable>
      ) : null}
    </>
  );

  const footer = completion ? (
    <>
      {next ? (
        <Button
          label={strings.lessons.next(next.title)}
          onPress={() =>
            router.replace({ pathname: "/lesson/[slug]", params: { slug: next.slug } })
          }
        />
      ) : null}
      <Button
        label={strings.lessons.finish}
        variant={next ? "ghost" : "primary"}
        onPress={() => router.back()}
      />
    </>
  ) : step && index !== null ? (
    <Button
      label={last ? strings.lessons.finishLesson : strings.onboarding.continue}
      onPress={() => (last ? void complete() : setIndex(index + 1))}
      loading={completing}
      disabled={!canContinue(step, answers)}
    />
  ) : null;

  let body: ReactNode = <LoadingBlocks count={3} />;
  if (completion) {
    body = (
      <CompletionView
        completion={completion}
        takeaways={steps.flatMap((s) => (s.type === "summary" ? s.points : []))}
        onRate={(rating) => api.attempts.rate(attemptId, rating)}
      />
    );
  } else if (step?.type === "question") {
    const question = data.content.questions.find((q) => q.id === step.question_id);
    body = question ? (
      <QuestionView
        key={question.id}
        question={question}
        result={answers[question.id]}
        onSubmit={(optionIds) => submit(question.id, optionIds)}
      />
    ) : null;
  } else if (step) {
    body = <StepView key={index} step={step} content={data.content} />;
  }

  return (
    <Frame header={header} footer={footer}>
      {body}
      {error ? <Banner message={error} tone="error" /> : null}
    </Frame>
  );
}

function CloseButton() {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={strings.lessons.close}
      onPress={() => router.back()}
      style={styles.iconButton}
    >
      <Text variant="heading">✕</Text>
    </Pressable>
  );
}

function Frame({
  header,
  footer,
  children,
}: {
  header: ReactNode;
  footer?: ReactNode;
  children: ReactNode;
}) {
  const { colors } = useTheme();
  return (
    <SafeAreaView style={[styles.root, { backgroundColor: colors.bg }]} edges={["top", "bottom"]}>
      <View style={[styles.column, styles.header]}>{header}</View>
      <ScrollView contentContainerStyle={styles.scroll}>
        <View style={styles.column}>{children}</View>
      </ScrollView>
      {footer ? <View style={[styles.column, styles.footer]}>{footer}</View> : null}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1 },
  flex: { flex: 1 },
  column: { width: "100%", maxWidth: readingMaxWidth, alignSelf: "center", gap: spacing.lg },
  header: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
  },
  iconButton: { minWidth: touchTarget, minHeight: touchTarget, justifyContent: "center" },
  scroll: { flexGrow: 1, paddingHorizontal: spacing.lg, paddingVertical: spacing.lg },
  footer: { paddingHorizontal: spacing.lg, paddingBottom: spacing.lg, gap: spacing.sm },
});
