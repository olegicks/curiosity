import AsyncStorage from "@react-native-async-storage/async-storage";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { router, useLocalSearchParams, usePreventRemove } from "expo-router";
import { type ReactNode, useCallback, useEffect, useState } from "react";
import { Alert, View } from "react-native";

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
import { HeaderButton, PlayerFrame, playerStyles } from "@/ui/PlayerFrame";
import { ErrorState, LoadingBlocks } from "@/ui/States";
import { useTheme } from "@/ui/theme";

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
    <PlayerFrame
      header={
        <HeaderButton label={strings.lessons.close} icon="close" onPress={() => router.back()} />
      }
    >
      {attempt.isError ? (
        <ErrorState message={errorMessage(attempt.error)} onRetry={() => void attempt.refetch()} />
      ) : (
        <LoadingBlocks count={3} />
      )}
    </PlayerFrame>
  );
}

function Player({ data }: { data: AttemptResponse }) {
  const { api } = useAuth();
  const { colors } = useTheme();
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
  // After answering, Continue takes the verdict's colour, like the feedback above it.
  const verdict = step?.type === "question" ? answers[step.question_id] : undefined;
  const verdictVariant = verdict ? (verdict.is_correct ? "success" : "danger") : "primary";
  const last = index === steps.length - 1;
  const next = completion?.next_lesson ?? null;

  const header = (
    <>
      <HeaderButton label={strings.lessons.close} icon="close" onPress={() => router.back()} />
      {index !== null && !completion ? (
        <ProgressBar
          value={index + 1}
          max={steps.length}
          label={strings.lessons.step(index + 1, steps.length)}
          height={16}
          color={colors.success}
        />
      ) : (
        <View style={playerStyles.spacer} />
      )}
      {index !== null && index > 0 && !completion ? (
        <HeaderButton
          label={strings.lessons.back}
          text={strings.lessons.back}
          onPress={() => setIndex(Math.max(index - 1, 0))}
        />
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
      variant={verdictVariant}
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
    <PlayerFrame header={header} footer={footer}>
      {body}
      {error ? <Banner message={error} tone="error" /> : null}
    </PlayerFrame>
  );
}
