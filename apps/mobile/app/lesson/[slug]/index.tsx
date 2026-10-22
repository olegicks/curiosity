import { useQuery } from "@tanstack/react-query";
import { router, useLocalSearchParams } from "expo-router";
import { Pressable, StyleSheet, View } from "react-native";

import { errorMessage } from "@/api/errors";
import { useAuth } from "@/features/auth/AuthProvider";
import { startLabel, statusLabel } from "@/features/lessons/library";
import { LessonRow } from "@/features/lessons/LessonRow";
import { strings } from "@/i18n/en";
import { Banner } from "@/ui/Banner";
import { Button } from "@/ui/Button";
import { Icon, type IconName } from "@/ui/Icon";
import { MasteryDots } from "@/ui/MasteryDots";
import { Screen } from "@/ui/Screen";
import { ErrorState, LoadingBlocks } from "@/ui/States";
import { Text } from "@/ui/Text";
import { useTheme } from "@/ui/theme";
import { edge, radius, spacing, touchTarget } from "@/ui/tokens";

/** Lesson intro (docs/spec/02 §2.7). */
export default function LessonIntroScreen() {
  const { slug } = useLocalSearchParams<{ slug: string }>();
  const { api } = useAuth();
  const { colors } = useTheme();
  const detail = useQuery({ queryKey: ["lesson", slug], queryFn: () => api.content.lesson(slug) });
  const lesson = detail.data?.lesson;
  const revisit =
    lesson?.progress.status !== "not_started" && !lesson?.progress.in_progress_attempt_id;

  return (
    <Screen
      footer={
        lesson ? (
          <>
            <Button
              label={startLabel(lesson.progress)}
              onPress={() => router.push({ pathname: "/lesson/[slug]/play", params: { slug } })}
            />
            {revisit ? (
              <Text variant="caption" tone="muted" style={styles.center}>
                {strings.lessons.revisitNote}
              </Text>
            ) : null}
          </>
        ) : null
      }
    >
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={strings.lessons.back}
        onPress={() => router.back()}
        style={styles.back}
      >
        <Text variant="label" tone="accent">
          ‹ {strings.lessons.back}
        </Text>
      </Pressable>
      {detail.isPending ? <LoadingBlocks count={3} /> : null}
      {detail.isError ? (
        <ErrorState message={errorMessage(detail.error)} onRetry={() => void detail.refetch()} />
      ) : null}
      {lesson ? (
        <>
          <View style={styles.hero}>
            <View
              style={[
                styles.heroIcon,
                { backgroundColor: colors.accent, borderColor: colors.accentEdge },
              ]}
            >
              <Icon name="sparkles" color={colors.onAccent} size={44} />
            </View>
            <Text variant="label" tone="accent">
              {lesson.topic.title.toUpperCase()}
            </Text>
            <Text variant="display" accessibilityRole="header" style={styles.center}>
              {lesson.title}
            </Text>
          </View>
          <View style={[styles.status, styles.centered]}>
            <Text variant="label">{statusLabel(lesson.progress)}</Text>
            {lesson.progress.mastery_stage > 0 ? (
              <MasteryDots stage={lesson.progress.mastery_stage} />
            ) : null}
          </View>
          <View
            style={[styles.goal, { backgroundColor: colors.surface, borderColor: colors.border }]}
          >
            <Text variant="label" tone="muted">
              {strings.lessons.objective}
            </Text>
            <Text variant="reading">{lesson.learning_objective}</Text>
          </View>
          <View style={styles.section}>
            {(
              [
                ["time-outline", strings.lessons.minutes(lesson.estimated_minutes)],
                ["help-circle-outline", strings.lessons.introChecks],
                ["bulb-outline", strings.lessons.introRecall],
              ] as [IconName, string][]
            ).map(([icon, text]) => (
              <View key={icon} style={styles.feature}>
                <Icon name={icon} color={colors.accent} size={24} />
                <Text style={styles.flex}>{text}</Text>
              </View>
            ))}
          </View>
          {lesson.evidence_status !== "established" ? (
            <Banner message={strings.lessons.debatedNote} />
          ) : null}
          {lesson.related.length > 0 ? (
            <View style={styles.section}>
              <Text variant="heading" accessibilityRole="header">
                {strings.lessons.related}
              </Text>
              {lesson.related.map((related) => (
                <LessonRow key={related.slug} lesson={related} />
              ))}
            </View>
          ) : null}
        </>
      ) : null}
    </Screen>
  );
}

const styles = StyleSheet.create({
  back: { minHeight: touchTarget, justifyContent: "center", alignSelf: "flex-start" },
  hero: { alignItems: "center", gap: spacing.sm, paddingVertical: spacing.md },
  heroIcon: {
    width: 104,
    height: 104,
    borderRadius: radius.full,
    borderBottomWidth: edge + 2,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: spacing.sm,
  },
  goal: { borderWidth: 2, borderRadius: radius.md, padding: spacing.lg, gap: spacing.xs },
  feature: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  flex: { flex: 1 },
  status: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  section: { gap: spacing.sm },
  center: { textAlign: "center" },
  centered: { justifyContent: "center" },
});
