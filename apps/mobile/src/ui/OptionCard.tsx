import { Pressable, StyleSheet, View } from "react-native";

import { strings } from "@/i18n/en";

import { Icon, type IconName } from "./Icon";
import { Text } from "./Text";
import { useTheme } from "./theme";
import { edge, radius, spacing, touchTarget } from "./tokens";

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

/** A chunky answer option. Results use icon + text + colour, never colour alone (§10.4). */
export function OptionCard({ text, state, multi, disabled, onPress, position, count }: Props) {
  const { colors } = useTheme();
  const looks: Record<
    OptionState,
    { border: string; bg: string; fg: string; icon: IconName | null }
  > = {
    idle: { border: colors.border, bg: colors.surface, fg: colors.textMuted, icon: null },
    selected: {
      border: colors.accent,
      bg: colors.accentBg,
      fg: colors.accent,
      icon: multi ? "checkbox" : "radio-button-on",
    },
    correct: {
      border: colors.success,
      bg: colors.successBg,
      fg: colors.success,
      icon: "checkmark-circle",
    },
    incorrect: {
      border: colors.danger,
      bg: colors.dangerBg,
      fg: colors.danger,
      icon: "close-circle",
    },
    missed: {
      border: colors.success,
      bg: colors.surface,
      fg: colors.success,
      icon: "checkmark-circle-outline",
    },
    locked: { border: colors.border, bg: colors.surface, fg: colors.textMuted, icon: null },
  };
  const look = looks[state];
  const status = {
    idle: "",
    selected: "selected",
    correct: "selected, correct",
    incorrect: "selected, incorrect",
    missed: strings.lessons.correctAnswer.toLowerCase(),
    locked: "",
  }[state];
  const letter = String.fromCharCode(64 + position);

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
      style={({ pressed }) => {
        const sunk = pressed && !disabled;
        return [
          styles.card,
          {
            borderColor: look.border,
            backgroundColor: look.bg,
            borderBottomWidth: sunk ? 2 : edge,
            marginTop: sunk ? edge - 2 : 0,
            opacity: state === "locked" ? 0.6 : 1,
          },
        ];
      }}
    >
      <View style={[styles.letter, { borderColor: look.border }]}>
        <Text variant="label" style={{ color: look.fg }} importantForAccessibility="no">
          {letter}
        </Text>
      </View>
      <Text variant="body" style={styles.text}>
        {text}
      </Text>
      <View style={styles.trailing}>
        {state === "missed" ? (
          <Text variant="caption" tone="success">
            {strings.lessons.correctAnswer}
          </Text>
        ) : null}
        {look.icon ? <Icon name={look.icon} color={look.fg} size={26} /> : null}
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: {
    minHeight: touchTarget + 12,
    borderWidth: 2,
    borderRadius: radius.md,
    padding: spacing.md,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
  },
  letter: {
    width: 30,
    height: 30,
    borderWidth: 2,
    borderRadius: radius.sm,
    alignItems: "center",
    justifyContent: "center",
  },
  text: { flex: 1 },
  trailing: { alignItems: "flex-end", gap: spacing.xs },
});
