import { router } from "expo-router";
import { Pressable, StyleSheet, View } from "react-native";

import type { LessonSummary } from "@/api/types";
import { strings } from "@/i18n/en";
import { MasteryDots } from "@/ui/MasteryDots";
import { Text } from "@/ui/Text";
import { useTheme } from "@/ui/theme";
import { radius, spacing, touchTarget } from "@/ui/tokens";

import { progressBucket, statusLabel } from "./library";

const STATUS_ICON = { not_started: "○", in_progress: "◐", completed: "●" } as const;

export function LessonRow({ lesson }: { lesson: LessonSummary }) {
  const { colors } = useTheme();
  const bucket = progressBucket(lesson.progress);
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={`${lesson.title}. ${statusLabel(lesson.progress)}. ${strings.lessons.minutes(lesson.estimated_minutes)}`}
      onPress={() => router.push({ pathname: "/lesson/[slug]", params: { slug: lesson.slug } })}
      style={({ pressed }) => [
        styles.row,
        { backgroundColor: colors.surface, borderColor: colors.border },
        pressed && { opacity: 0.9 },
      ]}
    >
      <Text variant="heading" tone="accent" importantForAccessibility="no">
        {STATUS_ICON[bucket]}
      </Text>
      <View style={styles.body}>
        <Text variant="heading">{lesson.title}</Text>
        <Text variant="body" tone="muted" numberOfLines={2}>
          {lesson.description}
        </Text>
        <View style={styles.meta}>
          <Text variant="caption" tone="muted">
            {strings.lessons.minutes(lesson.estimated_minutes)}
          </Text>
          {lesson.progress.mastery_stage > 0 ? (
            <MasteryDots stage={lesson.progress.mastery_stage} />
          ) : null}
        </View>
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  row: {
    minHeight: touchTarget + 28,
    borderWidth: 1,
    borderRadius: radius.md,
    padding: spacing.md,
    flexDirection: "row",
    gap: spacing.md,
  },
  body: { flex: 1, gap: spacing.xs },
  meta: { flexDirection: "row", alignItems: "center", gap: spacing.md },
});
