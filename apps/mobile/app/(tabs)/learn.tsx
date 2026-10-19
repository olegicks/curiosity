import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Pressable, StyleSheet, View } from "react-native";

import { errorMessage } from "@/api/errors";
import { useAuth } from "@/features/auth/AuthProvider";
import { groupByTopic, type LibraryFilter } from "@/features/lessons/library";
import { LessonRow } from "@/features/lessons/LessonRow";
import { strings } from "@/i18n/en";
import { Screen } from "@/ui/Screen";
import { ErrorState, LoadingBlocks } from "@/ui/States";
import { Text } from "@/ui/Text";
import { useTheme } from "@/ui/theme";
import { radius, spacing, touchTarget } from "@/ui/tokens";

const FILTERS: LibraryFilter[] = ["all", "not_started", "in_progress", "completed"];

/** Learn library: published lessons grouped by topic (docs/spec/02 §2.6). */
export default function LearnScreen() {
  const { api } = useAuth();
  const { colors } = useTheme();
  const [filter, setFilter] = useState<LibraryFilter>("all");
  const lessons = useQuery({ queryKey: ["lessons"], queryFn: api.content.lessons });
  const groups = groupByTopic(lessons.data?.items ?? [], filter);

  return (
    <Screen>
      <Text variant="title" accessibilityRole="header">
        {strings.lessons.libraryTitle}
      </Text>
      <View style={styles.chips} accessibilityRole="tablist">
        {FILTERS.map((value) => {
          const active = value === filter;
          return (
            <Pressable
              key={value}
              accessibilityRole="tab"
              accessibilityState={{ selected: active }}
              onPress={() => setFilter(value)}
              style={[
                styles.chip,
                {
                  backgroundColor: active ? colors.accent : colors.surface,
                  borderColor: active ? colors.accent : colors.border,
                },
              ]}
            >
              <Text variant="label" style={{ color: active ? colors.onAccent : colors.text }}>
                {strings.lessons.filters[value]}
              </Text>
            </Pressable>
          );
        })}
      </View>
      {lessons.isPending ? <LoadingBlocks count={4} /> : null}
      {lessons.isError ? (
        <ErrorState message={errorMessage(lessons.error)} onRetry={() => void lessons.refetch()} />
      ) : null}
      {lessons.isSuccess && groups.length === 0 ? (
        <Text tone="muted">
          {lessons.data.items.length === 0 ? strings.lessons.empty : strings.lessons.emptyFilter}
        </Text>
      ) : null}
      {groups.map((group) => (
        <View key={group.slug} style={styles.group}>
          <Text variant="label" tone="muted" accessibilityRole="header">
            {group.title.toUpperCase()}
          </Text>
          {group.lessons.map((lesson) => (
            <LessonRow key={lesson.slug} lesson={lesson} />
          ))}
        </View>
      ))}
    </Screen>
  );
}

const styles = StyleSheet.create({
  chips: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  chip: {
    minHeight: touchTarget - 8,
    paddingHorizontal: spacing.md,
    borderWidth: 1,
    borderRadius: radius.full,
    justifyContent: "center",
  },
  group: { gap: spacing.sm },
});
