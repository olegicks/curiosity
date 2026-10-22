import { useQuery } from "@tanstack/react-query";
import { router } from "expo-router";

import { errorMessage } from "@/api/errors";
import { useAuth } from "@/features/auth/AuthProvider";
import { buildPath, currentSlug } from "@/features/path/path";
import { PathView } from "@/features/path/PathView";
import { Screen } from "@/ui/Screen";
import { ErrorState, LoadingBlocks } from "@/ui/States";

/** Path home (D-16): the lesson library as a path, with streak, XP and due reviews on top. */
export default function PathScreen() {
  const { api } = useAuth();
  const discover = useQuery({ queryKey: ["discover"], queryFn: api.discover.get });
  const lessons = useQuery({ queryKey: ["lessons"], queryFn: api.content.lessons });
  const items = lessons.data?.items ?? [];
  const units = buildPath(items, currentSlug(items, discover.data));

  return (
    <Screen
      refreshing={discover.isRefetching || lessons.isRefetching}
      onRefresh={() => {
        void discover.refetch();
        void lessons.refetch();
      }}
    >
      {lessons.isPending ? <LoadingBlocks count={4} /> : null}
      {lessons.isError ? (
        <ErrorState message={errorMessage(lessons.error)} onRetry={() => void lessons.refetch()} />
      ) : null}
      {lessons.data ? (
        <PathView
          units={units}
          discover={discover.data}
          onOpenLesson={(slug) => router.push({ pathname: "/lesson/[slug]", params: { slug } })}
          onStartReview={() => router.push("/review")}
        />
      ) : null}
    </Screen>
  );
}
