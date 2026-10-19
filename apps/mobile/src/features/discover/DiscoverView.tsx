import { Pressable, ScrollView, StyleSheet, View } from "react-native";

import type { DiscoverOut, LessonSummary } from "@/api/types";
import { LessonRow } from "@/features/lessons/LessonRow";
import { toDay } from "@/features/reviews/recall";
import { strings } from "@/i18n/en";
import { Button } from "@/ui/Button";
import { ProgressBar } from "@/ui/ProgressBar";
import { Text } from "@/ui/Text";
import { useTheme } from "@/ui/theme";
import { radius, spacing, touchTarget } from "@/ui/tokens";

import {
  type Destination,
  greeting,
  primaryCard,
  showTodaysLessonCard,
  streakA11yLabel,
} from "./discover";

type Props = {
  discover: DiscoverOut;
  displayName: string | null;
  now: Date;
  onNavigate: (destination: Destination) => void;
  onOpenProfile: () => void;
};

/** Discover: one obvious next action and a few calm signals (docs/spec/02 §2.5). */
export function DiscoverView({ discover, displayName, now, onNavigate, onOpenProfile }: Props) {
  const { colors } = useTheme();
  const card = primaryCard(discover, toDay(now));
  const { xp, streak, progress } = discover;
  const initial = (displayName ?? "?").slice(0, 1).toUpperCase();

  return (
    <View style={styles.stack}>
      <View style={styles.header}>
        <View style={styles.headerText}>
          <Text variant="title" accessibilityRole="header">
            {greeting(now.getHours(), displayName)}
          </Text>
          <View style={styles.signals}>
            <View
              accessible
              accessibilityLabel={streakA11yLabel(discover)}
              style={[styles.pill, { backgroundColor: colors.surfaceMuted }]}
            >
              <Text variant="label" importantForAccessibility="no">
                🔥 {streak.current}
              </Text>
            </View>
            <View
              accessible
              accessibilityLabel={
                xp.today >= xp.goal
                  ? strings.discover.goalReached
                  : strings.discover.xpToday(xp.today, xp.goal)
              }
              style={[styles.pill, styles.xpPill, { backgroundColor: colors.surfaceMuted }]}
            >
              <Text variant="label" importantForAccessibility="no">
                {strings.discover.xpToday(xp.today, xp.goal)}
              </Text>
              <ProgressBar value={Math.min(xp.today, xp.goal)} max={xp.goal} label="" />
            </View>
          </View>
        </View>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={strings.profile.title}
          onPress={onOpenProfile}
          style={[styles.avatar, { backgroundColor: colors.surfaceMuted }]}
        >
          <Text variant="label">{initial}</Text>
        </Pressable>
      </View>

      <View
        style={[styles.primary, { backgroundColor: colors.surface, borderColor: colors.accent }]}
      >
        <Text variant="label" tone="accent">
          {card.eyebrow}
        </Text>
        <Text variant="title">{card.title}</Text>
        {card.body ? <Text tone="muted">{card.body}</Text> : null}
        <Button label={card.cta} onPress={() => onNavigate(card.destination)} />
      </View>

      {showTodaysLessonCard(discover) && discover.todays_lesson ? (
        <View style={styles.section}>
          <Text variant="label" tone="muted" accessibilityRole="header">
            {strings.discover.todaysLesson.toUpperCase()}
          </Text>
          <LessonRow lesson={discover.todays_lesson} />
        </View>
      ) : null}

      {discover.recommended.length > 0 ? (
        <View style={styles.section}>
          <Text variant="label" tone="muted" accessibilityRole="header">
            {strings.discover.recommended.toUpperCase()}
          </Text>
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={styles.carousel}
          >
            {discover.recommended.map((lesson) => (
              <CompactLessonCard
                key={lesson.slug}
                lesson={lesson}
                onPress={() => onNavigate({ kind: "lesson", slug: lesson.slug })}
              />
            ))}
          </ScrollView>
        </View>
      ) : null}

      <Pressable
        accessibilityRole="button"
        accessibilityLabel={strings.discover.progress(
          progress.completed,
          progress.lessons_total,
          progress.understood,
        )}
        onPress={onOpenProfile}
        style={styles.progress}
      >
        <Text variant="label" importantForAccessibility="no">
          {strings.discover.progress(
            progress.completed,
            progress.lessons_total,
            progress.understood,
          )}
        </Text>
        <ProgressBar value={progress.completed} max={progress.lessons_total} label="" />
      </Pressable>
    </View>
  );
}

function CompactLessonCard({ lesson, onPress }: { lesson: LessonSummary; onPress: () => void }) {
  const { colors } = useTheme();
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={`${lesson.title}. ${strings.lessons.minutes(lesson.estimated_minutes)}`}
      onPress={onPress}
      style={({ pressed }) => [
        styles.compact,
        { backgroundColor: colors.surface, borderColor: colors.border },
        pressed && { opacity: 0.9 },
      ]}
    >
      <Text variant="caption" tone="muted">
        {lesson.topic.title.toUpperCase()}
      </Text>
      <Text variant="heading" numberOfLines={2}>
        {lesson.title}
      </Text>
      <Text variant="caption" tone="muted">
        {strings.lessons.minutes(lesson.estimated_minutes)}
      </Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  stack: { gap: spacing.xl },
  header: { flexDirection: "row", alignItems: "flex-start", gap: spacing.md },
  headerText: { flex: 1, gap: spacing.sm },
  signals: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  pill: {
    minHeight: touchTarget - 12,
    paddingHorizontal: spacing.md,
    borderRadius: radius.full,
    justifyContent: "center",
  },
  xpPill: { flexDirection: "row", alignItems: "center", gap: spacing.sm, minWidth: 150 },
  avatar: {
    width: touchTarget,
    height: touchTarget,
    borderRadius: radius.full,
    alignItems: "center",
    justifyContent: "center",
  },
  primary: { borderWidth: 2, borderRadius: radius.lg, padding: spacing.xl, gap: spacing.md },
  section: { gap: spacing.sm },
  carousel: { gap: spacing.md, paddingRight: spacing.lg },
  compact: {
    width: 180,
    minHeight: 120,
    borderWidth: 1,
    borderRadius: radius.md,
    padding: spacing.md,
    gap: spacing.xs,
  },
  progress: { gap: spacing.sm, minHeight: touchTarget, justifyContent: "center" },
});
