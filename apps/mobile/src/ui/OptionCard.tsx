import { Pressable, StyleSheet, View } from "react-native";

import { strings } from "@/i18n/en";

import { Text } from "./Text";
import { useTheme } from "./theme";
import { radius, spacing, touchTarget } from "./tokens";

export type OptionState =
  | "idle"
  | "selected"
  | "correct" // chosen and correct
  | "incorrect" // chosen and wrong
  | "missed" // correct but not chosen
  | "locked"; // not chosen, not correct, after answering

type Props = {
  text: string;
  state: OptionState;
  multi: boolean;
  disabled: boolean;
  onPress: () => void;
  position: number;
  count: number;
};

/** An answer option. Results use icon + text + colour, never colour alone (§10.4). */
export function OptionCard({ text, state, multi, disabled, onPress, position, count }: Props) {
  const { colors } = useTheme();
  const look = {
    idle: { border: colors.border, bg: colors.surface, icon: multi ? "□" : "○", width: 1 },
    selected: { border: colors.accent, bg: colors.surface, icon: multi ? "☑" : "◉", width: 2 },
    correct: { border: colors.success, bg: colors.successBg, icon: "✓", width: 2 },
    incorrect: { border: colors.danger, bg: colors.dangerBg, icon: "✕", width: 2 },
    missed: { border: colors.success, bg: colors.surface, icon: "✓", width: 2 },
    locked: { border: colors.border, bg: colors.surface, icon: "", width: 1 },
  }[state];
  const status = {
    idle: "",
    selected: "selected",
    correct: "selected, correct",
    incorrect: "selected, incorrect",
    missed: strings.lessons.correctAnswer.toLowerCase(),
    locked: "",
  }[state];

  return (
    <Pressable
      accessibilityRole={multi ? "checkbox" : "radio"}
      accessibilityState={{
        checked: state === "selected" || state === "correct" || state === "incorrect",
        disabled,
      }}
      accessibilityLabel={`Option ${position} of ${count}: ${text}${status ? `, ${status}` : ""}`}
      disabled={disabled}
      onPress={onPress}
      style={({ pressed }) => [
        styles.card,
        { borderColor: look.border, backgroundColor: look.bg, borderWidth: look.width },
        pressed && !disabled && { opacity: 0.9 },
      ]}
    >
      <Text variant="body" style={styles.text}>
        {text}
      </Text>
      <View style={styles.trailing}>
        {state === "missed" ? (
          <Text variant="caption" tone="success">
            {strings.lessons.correctAnswer}
          </Text>
        ) : null}
        <Text
          variant="heading"
          importantForAccessibility="no"
          style={{
            color:
              state === "incorrect"
                ? colors.danger
                : state === "correct" || state === "missed"
                  ? colors.success
                  : colors.accent,
          }}
        >
          {look.icon}
        </Text>
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: {
    minHeight: touchTarget + 8,
    borderRadius: radius.md,
    padding: spacing.md,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
  },
  text: { flex: 1 },
  trailing: { alignItems: "flex-end", gap: spacing.xs },
});
