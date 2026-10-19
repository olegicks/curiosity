import { useQuery, useQueryClient } from "@tanstack/react-query";
import { router, usePreventRemove } from "expo-router";
import { type ReactNode, useCallback, useMemo, useState } from "react";
import { Alert, View } from "react-native";

import { ApiError, errorMessage } from "@/api/errors";
import type {
  Achievement,
  ReviewAnswerResult,
  ReviewSessionResponse,
  ReviewSessionSummary,
} from "@/api/types";
import { useAuth } from "@/features/auth/AuthProvider";
import { firstOpenItem } from "@/features/reviews/recall";
import { ReviewItemView } from "@/features/reviews/ReviewItemView";
import { SessionSummaryView } from "@/features/reviews/SessionSummaryView";
import { strings } from "@/i18n/en";
import { Banner } from "@/ui/Banner";
import { Button } from "@/ui/Button";
import { HeaderButton, PlayerFrame, playerStyles } from "@/ui/PlayerFrame";
import { ProgressBar } from "@/ui/ProgressBar";
import { ErrorState, LoadingBlocks } from "@/ui/States";
import { Text } from "@/ui/Text";

const AFFECTED_QUERIES = ["reviews", "lessons", "lesson", "discover", "progress"];

/** Review session (docs/spec/02 §2.11). The server picks items and schedules answers. */
export default function ReviewSessionScreen() {
  const { api } = useAuth();
  // Idempotent: returns today's open session or creates one from the due items.
  const session = useQuery({
    queryKey: ["review-session"],
    queryFn: api.reviews.startSession,
    staleTime: Infinity,
    gcTime: 0,
    retry: false,
    refetchOnWindowFocus: false,
  });

  if (session.data) return <Session key={session.data.session.id} data={session.data} />;

  const nothingDue = session.error instanceof ApiError && session.error.code === "NOTHING_DUE";
  return (
    <PlayerFrame
      header={<HeaderButton label={strings.lessons.close} text="✕" onPress={() => router.back()} />}
      footer={
        nothingDue ? <Button label={strings.recall.done} onPress={() => router.back()} /> : null
      }
    >
      {session.isPending ? <LoadingBlocks count={3} /> : null}
      {nothingDue ? <Text variant="title">{strings.recall.nothingDue}</Text> : null}
      {session.isError && !nothingDue ? (
        <ErrorState message={errorMessage(session.error)} onRetry={() => void session.refetch()} />
      ) : null}
    </PlayerFrame>
  );
}

function Session({ data }: { data: ReviewSessionResponse }) {
  const { api } = useAuth();
  const queryClient = useQueryClient();
  const { id: sessionId, items } = data.session;

  const [results, setResults] = useState<Record<string, ReviewAnswerResult>>(() =>
    Object.fromEntries(
      items.flatMap((item) => (item.result ? [[item.id, item.result] as const] : [])),
    ),
  );
  const [index, setIndex] = useState(() => Math.min(firstOpenItem(items), items.length - 1));
  const [summary, setSummary] = useState<ReviewSessionSummary | null>(data.summary ?? null);
  const [completed, setCompleted] = useState(false);
  const [streak, setStreak] = useState<number | null>(null);
  const [achievements, setAchievements] = useState<Achievement[]>([]);
  const [showSummary, setShowSummary] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const titles = useMemo(
    () => Object.fromEntries(items.map((item) => [item.lesson.slug, item.lesson.title])),
    [items],
  );

  const refreshAppData = useCallback(() => {
    for (const key of AFFECTED_QUERIES) void queryClient.invalidateQueries({ queryKey: [key] });
  }, [queryClient]);

  const submit = useCallback(
    async (itemId: string, optionIds: string[], guessed: boolean) => {
      const response = await api.reviews.answer(sessionId, itemId, optionIds, guessed);
      setResults((current) => ({ ...current, [itemId]: response.result }));
      setAchievements((current) => [...current, ...response.achievements_unlocked]);
      if (response.session_summary) {
        setSummary(response.session_summary);
        setCompleted(true);
        setStreak(response.streak?.current ?? null);
      }
      refreshAppData();
      return response.result;
    },
    [api, sessionId, refreshAppData],
  );

  // Ending early keeps answers; unanswered items simply stay due.
  const finished = showSummary || completed;
  usePreventRemove(!finished, () => {
    Alert.alert(strings.recall.endTitle, strings.recall.endBody, [
      { text: strings.recall.keepGoing, style: "cancel" },
      {
        text: strings.recall.end,
        style: "destructive",
        onPress: () => {
          api.reviews
            .endSession(sessionId)
            .then((ended) => {
              setSummary(ended.summary ?? null);
              setShowSummary(true);
              refreshAppData();
            })
            .catch((e: unknown) => setError(errorMessage(e)));
        },
      },
    ]);
  });

  const item = items[index];
  const answered = item ? item.id in results : false;
  const last = index >= items.length - 1;

  let body: ReactNode = null;
  let footer: ReactNode = null;
  if (showSummary && summary) {
    body = (
      <SessionSummaryView
        summary={summary}
        completed={completed}
        titles={titles}
        streak={streak}
        achievements={achievements}
      />
    );
    footer = <Button label={strings.recall.done} onPress={() => router.back()} />;
  } else if (item) {
    body = (
      <ReviewItemView
        key={item.id}
        item={item}
        result={results[item.id]}
        onSubmit={(ids, guessed) => submit(item.id, ids, guessed)}
      />
    );
    footer = answered ? (
      <Button
        label={last ? strings.recall.summaryTitle : strings.recall.next}
        onPress={() => (last ? setShowSummary(true) : setIndex(index + 1))}
        disabled={last && !summary}
      />
    ) : null;
  }

  return (
    <PlayerFrame
      header={
        <>
          <HeaderButton label={strings.recall.end} text="✕" onPress={() => router.back()} />
          {!showSummary ? (
            <ProgressBar
              value={Object.keys(results).length}
              max={items.length}
              label={strings.recall.item(index + 1, items.length)}
            />
          ) : (
            <View style={playerStyles.spacer} />
          )}
        </>
      }
      footer={footer}
    >
      {body}
      {error ? <Banner message={error} tone="error" /> : null}
    </PlayerFrame>
  );
}
