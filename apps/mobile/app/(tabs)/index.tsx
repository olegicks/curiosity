import { useQuery } from "@tanstack/react-query";
import { router } from "expo-router";

import { errorMessage } from "@/api/errors";
import { useAuth } from "@/features/auth/AuthProvider";
import { buildPath, currentSlug } from "@/features/path/path";
import { PathView } from "@/features/path/PathView";
import { Tour, useTour } from "@/features/path/Tour";
import { useSubject } from "@/features/subjects/SubjectProvider";
import { activeSubject, lessonsOf, subjectLook } from "@/features/subjects/subjects";
import { Screen } from "@/ui/Screen";
import { ErrorState, LoadingBlocks } from "@/ui/States";

/** Path home (D-16, D-17): the chosen subject's roadmap with streak, XP and recall on top. */
export default function PathScreen() {
  const { api } = useAuth();
  const { stored } = useSubject();
  const tour = useTour();
  const discover = useQuery({ queryKey: ["discover"], queryFn: api.discover.get });
  const lessons = useQuery({ queryKey: ["lessons"], queryFn: api.content.lessons });
  const subjects = useQuery({ queryKey: ["subjects"], queryFn: api.content.subjects });

  const list = subjects.data?.items ?? [];
  const subject = activeSubject(list, stored);
  const items = lessonsOf(lessons.data?.items ?? [], subject?.slug ?? null);
  // the server's suggestion only counts when it belongs to this subject
  const suggestion =
    discover.data && subject
      ? {
          ...discover.data,
          primary_action:
            discover.data.primary_action.lesson?.subject.slug === subject.slug
              ? discover.data.primary_action
              : { type: "review" as const },
          todays_lesson:
            discover.data.todays_lesson?.subject.slug === subject.slug
              ? discover.data.todays_lesson
              : null,
        }
      : discover.data;
  const units = buildPath(items, currentSlug(items, suggestion));

  return (
    <Screen
      refreshing={discover.isRefetching || lessons.isRefetching}
      onRefresh={() => {
        void discover.refetch();
        void lessons.refetch();
        void subjects.refetch();
      }}
    >
      {lessons.isPending || subjects.isPending ? <LoadingBlocks count={4} /> : null}
      {lessons.isError ? (
        <ErrorState message={errorMessage(lessons.error)} onRetry={() => void lessons.refetch()} />
      ) : null}
      {lessons.data && subjects.data ? (
        <PathView
          subject={
            subject
              ? { title: subject.title, ...subjectLook(subject.slug, list.indexOf(subject)) }
              : null
          }
          units={units}
          discover={discover.data}
          onSwitchSubject={() => router.push("/subjects")}
          onOpenLesson={(slug) => router.push({ pathname: "/lesson/[slug]", params: { slug } })}
          onPlayLesson={(slug) =>
            router.push({ pathname: "/lesson/[slug]/play", params: { slug } })
          }
          onStartReview={() => router.push("/review")}
        />
      ) : null}
      <Tour visible={tour.visible && lessons.isSuccess} onDone={tour.finish} />
    </Screen>
  );
}
