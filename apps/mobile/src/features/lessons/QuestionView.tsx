import { useState } from "react";
import { StyleSheet, View } from "react-native";

import { errorMessage } from "@/api/errors";
import type { AnswerResult, QuestionOut } from "@/api/types";
import { strings } from "@/i18n/en";
import { haptics } from "@/lib/haptics";
import { Banner } from "@/ui/Banner";
import { Button } from "@/ui/Button";
import { Card } from "@/ui/Card";
import { OptionCard } from "@/ui/OptionCard";
import { Text } from "@/ui/Text";
import { spacing } from "@/ui/tokens";

import { feedbackLines, isSingleAnswer, optionState, toggleSelection } from "./player";

type Props = {
  question: QuestionOut;
  result: AnswerResult | undefined;
  /** Sends the answer; the server grades it. */
  onSubmit: (optionIds: string[]) => Promise<AnswerResult>;
};

/** Select -> Check -> server feedback (docs/spec/02 FR-LRN-4). No local grading. */
export function QuestionView({ question, result, onSubmit }: Props) {
  const [selection, setSelection] = useState<string[]>([]);
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const multi = !isSingleAnswer(question);
  const locked = checking || result !== undefined;

  const select = (optionId: string) => {
    if (locked) return;
    haptics.select();
    setSelection((current) => toggleSelection(question, current, optionId));
  };

  const check = async () => {
    setChecking(true);
    setError(null);
    try {
      const answer = await onSubmit(selection);
      haptics.result(answer.is_correct);
    } catch (e) {
      setError(errorMessage(e)); // options unlock so the learner can retry
    } finally {
      setChecking(false);
    }
  };

  return (
    <View style={styles.stack}>
      <Text variant="title" accessibilityRole="header">
        {question.prompt}
      </Text>
      {multi && !result ? (
        <Text variant="label" tone="muted">
          {strings.lessons.selectAll}
          {selection.length ? ` · ${strings.lessons.selected(selection.length)}` : ""}
        </Text>
      ) : null}
      <View style={styles.options}>
        {question.options.map((option, i) => (
          <OptionCard
            key={option.id}
            text={option.text}
            state={optionState(option.id, selection, result)}
            multi={multi}
            disabled={locked}
            onPress={() => select(option.id)}
            position={i + 1}
            count={question.options.length}
          />
        ))}
      </View>
      {error ? <Banner message={error} tone="error" /> : null}
      {result ? (
        <View accessibilityLiveRegion="polite">
          <Card tone={result.is_correct ? "success" : "danger"}>
            <Text variant="heading" tone={result.is_correct ? "success" : "danger"}>
              {result.is_correct ? `✓ ${strings.lessons.correct}` : `✕ ${strings.lessons.notQuite}`}
            </Text>
            {feedbackLines(result).map((line, i) => (
              <Text key={i}>{line}</Text>
            ))}
          </Card>
        </View>
      ) : (
        <Button
          label={strings.lessons.check}
          onPress={check}
          loading={checking}
          disabled={selection.length === 0}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  stack: { gap: spacing.lg },
  options: { gap: spacing.sm },
});
