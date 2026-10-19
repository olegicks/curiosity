import { useQuery } from "@tanstack/react-query";
import { router } from "expo-router";
import { Pressable, StyleSheet, View } from "react-native";

import { errorMessage } from "@/api/errors";
import type { Concept } from "@/api/types";
import { useAuth } from "@/features/auth/AuthProvider";
import { dueCountLabel, dueLabel, friendlyDay, toDay } from "@/features/reviews/recall";
import { strings } from "@/i18n/en";
import { Button } from "@/ui/Button";
import { Card } from "@/ui/Card";
import { MasteryDots } from "@/ui/MasteryDots";
import { Screen } from "@/ui/Screen";
import { ErrorState, LoadingBlocks } from "@/ui/States";
import { Text } from "@/ui/Text";
import { useTheme } from "@/ui/theme";
import { radius, spacing, touchTarget } from "@/ui/tokens";

/** Recall tab: what's due and every concept in review (docs/spec/02 §2.10). */
export default function RecallScreen() {
  const { api } = useAuth();
  const summary = useQuery({ queryKey: ["reviews", "summary"], queryFn: api.reviews.summary });
  const concepts = useQuery({ queryKey: ["reviews", "concepts"], queryFn: api.reviews.concepts });
  const today = toDay(new Date());
  const refetch = () => {
    void summary.refetch();
    void concepts.refetch();
  };

  return (
    <Screen>
      <Text variant="title" accessibilityRole="header">
        {strings.recall.title}
      </Text>
      {summary.isPending ? <LoadingBlocks count={2} /> : null}
      {summary.isError ? (
        <ErrorState message={errorMessage(summary.error)} onRetry={refetch} />
      ) : null}
      {summary.data ? (
        <Card>
          {summary.data.in_review_count === 0 ? (
            <>
              <Text>{strings.recall.noConcepts}</Text>
              <Button
                label={strings.recall.goLearn}
                variant="secondary"
                onPress={() => router.push("/learn")}
              />
            </>
          ) : summary.data.due_count > 0 || summary.data.open_session_id ? (
            <>
              <Text variant="heading">
                {strings.recall.dueCount(dueCountLabel(summary.data.due_count))}
              </Text>
              <Text tone="muted">{strings.recall.inReview(summary.data.in_review_count)}</Text>
              <Button
                label={
                  summary.data.open_session_id
                    ? strings.recall.resume
                    : strings.recall.start(dueCountLabel(summary.data.due_count))
                }
                onPress={() => router.push("/review")}
              />
            </>
          ) : (
            <>
              <Text variant="heading">
                {strings.recall.caughtUp(
                  summary.data.next_due_on
                    ? friendlyDay(summary.data.next_due_on, today)
                    : strings.recall.tomorrow,
                )}
              </Text>
              <Text tone="muted">{strings.recall.inReview(summary.data.in_review_count)}</Text>
            </>
          )}
        </Card>
      ) : null}

      {concepts.data && concepts.data.items.length > 0 ? (
        <View style={styles.list}>
          <Text variant="label" tone="muted" accessibilityRole="header">
            {strings.recall.concepts.toUpperCase()}
          </Text>
          {concepts.data.items.map((concept) => (
            <ConceptRow key={concept.lesson.slug} concept={concept} today={today} />
          ))}
        </View>
      ) : null}
    </Screen>
  );
}

function ConceptRow({ concept, today }: { concept: Concept; today: string }) {
  const { colors } = useTheme();
  const due = dueLabel(concept.due_on, today);
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={`${concept.lesson.title}. ${due}. ${strings.lessons.mastery(concept.mastery_stage)}`}
      onPress={() =>
        router.push({ pathname: "/lesson/[slug]", params: { slug: concept.lesson.slug } })
      }
      style={({ pressed }) => [
        styles.row,
        { backgroundColor: colors.surface, borderColor: colors.border },
        pressed && { opacity: 0.9 },
      ]}
    >
      <View style={styles.rowText}>
        <Text variant="heading">{concept.lesson.title}</Text>
        <Text variant="caption" tone={concept.is_due ? "accent" : "muted"}>
          {due}
        </Text>
      </View>
      <MasteryDots stage={concept.mastery_stage} />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  list: { gap: spacing.sm },
  row: {
    minHeight: touchTarget + 16,
    borderWidth: 1,
    borderRadius: radius.md,
    padding: spacing.md,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
  },
  rowText: { flex: 1, gap: spacing.xs },
});
