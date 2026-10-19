import { useState } from "react";
import { StyleSheet, View } from "react-native";

import type { CompletionResponse } from "@/api/types";
import { strings } from "@/i18n/en";
import { Button } from "@/ui/Button";
import { Card } from "@/ui/Card";
import { Markdown } from "@/ui/Markdown";
import { Text } from "@/ui/Text";
import { spacing } from "@/ui/tokens";

import { xpLabel } from "./library";

type Props = {
  completion: CompletionResponse;
  takeaways: string[];
  onRate: (rating: "clear" | "unclear") => Promise<void>;
};

const MAX_ACHIEVEMENTS_SHOWN = 2;

/** Completion screen content (docs/spec/02 FR-LRN-6). Actions live in the player footer. */
export function CompletionView({ completion, takeaways, onRate }: Props) {
  const [rated, setRated] = useState(false);
  const { attempt, xp_awarded, achievements_unlocked, first_review_on } = completion;

  const rate = async (rating: "clear" | "unclear") => {
    setRated(true);
    await onRate(rating).catch(() => setRated(false));
  };

  return (
    <View style={styles.stack}>
      <Text variant="display" accessibilityRole="header">
        {strings.lessons.completeTitle}
      </Text>
      <Text variant="heading">
        {strings.lessons.score(attempt.correct_first_try, attempt.question_count)}
      </Text>
      {takeaways.length > 0 ? (
        <Markdown source={takeaways.map((t) => `- ${t}`).join("\n")} />
      ) : null}
      {first_review_on ? <Text tone="muted">{strings.lessons.firstReview}</Text> : null}

      <Card>
        <Text variant="label" tone="muted">
          {strings.lessons.xpEarned}
        </Text>
        {xp_awarded.length === 0 ? <Text>{strings.lessons.noXpRevisit}</Text> : null}
        {xp_awarded.map((award) => (
          <View key={award.reason} style={styles.xpRow}>
            <Text>{xpLabel(award.reason)}</Text>
            <Text variant="label" tone="accent">
              +{award.amount} XP
            </Text>
          </View>
        ))}
      </Card>

      {achievements_unlocked.slice(0, MAX_ACHIEVEMENTS_SHOWN).map((a) => (
        <Card key={a.code} tone="success">
          <Text variant="label" tone="success">
            {strings.lessons.unlocked}
          </Text>
          <Text variant="heading">{a.title}</Text>
          <Text tone="muted">{a.description}</Text>
        </Card>
      ))}

      <View style={styles.rating}>
        <Text variant="label">{rated ? strings.lessons.thanks : strings.lessons.wasClear}</Text>
        {!rated ? (
          <View style={styles.ratingButtons}>
            <Button
              label={strings.lessons.clear}
              variant="secondary"
              onPress={() => rate("clear")}
            />
            <Button
              label={strings.lessons.unclear}
              variant="secondary"
              onPress={() => rate("unclear")}
            />
          </View>
        ) : null}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  stack: { gap: spacing.lg },
  xpRow: { flexDirection: "row", justifyContent: "space-between" },
  rating: { gap: spacing.sm },
  ratingButtons: { flexDirection: "row", gap: spacing.sm },
});
