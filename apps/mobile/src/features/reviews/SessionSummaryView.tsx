import { router } from "expo-router";
import { StyleSheet, View } from "react-native";

import type { Achievement, ReviewSessionSummary } from "@/api/types";
import { strings } from "@/i18n/en";
import { Button } from "@/ui/Button";
import { Card } from "@/ui/Card";
import { Text } from "@/ui/Text";
import { spacing } from "@/ui/tokens";

import { stageName } from "./recall";

type Props = {
  summary: ReviewSessionSummary;
  completed: boolean;
  titles: Record<string, string>; // lesson slug -> title
  streak: number | null;
  achievements: Achievement[];
};

/** Session summary (docs/spec/02 §2.11). */
export function SessionSummaryView({ summary, completed, titles, streak, achievements }: Props) {
  return (
    <View style={styles.stack}>
      <Text variant="display" accessibilityRole="header">
        {completed ? strings.recall.summaryTitle : strings.recall.endedTitle}
      </Text>
      <Text variant="heading">{strings.recall.score(summary.correct, summary.total)}</Text>
      <View style={styles.row}>
        {summary.xp_total > 0 ? (
          <Text variant="label" tone="accent">
            {strings.recall.xp(summary.xp_total)}
          </Text>
        ) : null}
        {streak ? <Text variant="label">{strings.recall.streak(streak)}</Text> : null}
      </View>

      {summary.advanced.length > 0 ? (
        <Card tone="success">
          <Text variant="label" tone="success">
            {strings.recall.advanced}
          </Text>
          {summary.advanced.map((a) => (
            <Text key={a.slug}>
              {strings.recall.advancedItem(
                titles[a.slug] ?? a.slug,
                stageName(a.from),
                stageName(a.to),
              )}
            </Text>
          ))}
        </Card>
      ) : null}

      {summary.to_revisit.length > 0 ? (
        <Card>
          <Text variant="label" tone="muted">
            {strings.recall.toRevisit}
          </Text>
          {summary.to_revisit.map((lesson) => (
            <Button
              key={lesson.slug}
              label={lesson.title}
              variant="ghost"
              onPress={() =>
                router.push({ pathname: "/lesson/[slug]", params: { slug: lesson.slug } })
              }
            />
          ))}
        </Card>
      ) : null}

      {achievements.slice(0, 2).map((a) => (
        <Card key={a.code} tone="success">
          <Text variant="label" tone="success">
            {strings.lessons.unlocked}
          </Text>
          <Text variant="heading">{a.title}</Text>
          <Text tone="muted">{a.description}</Text>
        </Card>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  stack: { gap: spacing.lg },
  row: { flexDirection: "row", gap: spacing.lg },
});
