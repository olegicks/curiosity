import { router } from "expo-router";
import { useState } from "react";
import { StyleSheet, Switch, View } from "react-native";

import type { ReviewAnswerResult, ReviewItem } from "@/api/types";
import { QuestionView } from "@/features/lessons/QuestionView";
import { strings } from "@/i18n/en";
import { Button } from "@/ui/Button";
import { Card } from "@/ui/Card";
import { MasteryDots } from "@/ui/MasteryDots";
import { Text } from "@/ui/Text";
import { useTheme } from "@/ui/theme";
import { spacing } from "@/ui/tokens";

import { scheduleMessage, stageName } from "./recall";

type Props = {
  item: ReviewItem;
  result: ReviewAnswerResult | undefined;
  onSubmit: (optionIds: string[], guessed: boolean) => Promise<ReviewAnswerResult>;
};

/** One review item: active recall with an optional "I'm guessing" signal (D-4). */
export function ReviewItemView({ item, result, onSubmit }: Props) {
  const { colors } = useTheme();
  const [guessed, setGuessed] = useState(false);

  return (
    <View style={styles.stack}>
      <Text variant="label" tone="muted">
        {strings.recall.concept(item.lesson.title)}
      </Text>
      <QuestionView
        question={item.question}
        result={result}
        onSubmit={(ids) => onSubmit(ids, guessed)}
        beforeCheck={
          <View style={styles.guess}>
            <View style={styles.guessText}>
              <Text variant="label">{strings.recall.guessing}</Text>
              <Text variant="caption" tone="muted">
                {strings.recall.guessingHint}
              </Text>
            </View>
            <Switch
              accessibilityLabel={strings.recall.guessing}
              value={guessed}
              onValueChange={setGuessed}
              trackColor={{ true: colors.accent, false: colors.border }}
            />
          </View>
        }
        afterFeedback={
          result ? (
            <Card>
              <Text variant="heading">{scheduleMessage(result)}</Text>
              <View style={styles.stage}>
                <MasteryDots stage={result.mastery_stage.after} />
                <Text variant="label">
                  {strings.recall.now(stageName(result.mastery_stage.after))}
                </Text>
              </View>
              {!result.is_correct ? (
                <Button
                  label={strings.recall.revisitLesson}
                  variant="secondary"
                  onPress={() =>
                    router.push({ pathname: "/lesson/[slug]", params: { slug: item.lesson.slug } })
                  }
                />
              ) : null}
            </Card>
          ) : null
        }
      />
    </View>
  );
}

const styles = StyleSheet.create({
  stack: { gap: spacing.md },
  guess: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  guessText: { flex: 1, gap: spacing.xs },
  stage: { flexDirection: "row", alignItems: "center", gap: spacing.md },
});
