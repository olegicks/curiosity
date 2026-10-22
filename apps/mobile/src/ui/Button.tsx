import { ActivityIndicator, Pressable, StyleSheet, View } from "react-native";

import { Text } from "./Text";
import { useTheme } from "./theme";
import { edge, radius, spacing, touchTarget } from "./tokens";

export type ButtonVariant =
  "primary" | "success" | "danger" | "secondary" | "ghost" | "destructive";

type Props = {
  label: string;
  onPress: () => void;
  variant?: ButtonVariant;
  disabled?: boolean;
  loading?: boolean;
  accessibilityHint?: string;
};

/** Chunky button: a darker bottom edge that the face sinks into when pressed (D-16). */
export function Button({
  label,
  onPress,
  variant = "primary",
  disabled = false,
  loading = false,
  accessibilityHint,
}: Props) {
  const { colors } = useTheme();
  const inactive = disabled || loading;
  const look = {
    primary: { bg: colors.accent, fg: colors.onAccent, edge: colors.accentEdge, border: 0 },
    success: { bg: colors.success, fg: colors.onAccent, edge: colors.successEdge, border: 0 },
    danger: { bg: colors.danger, fg: colors.onAccent, edge: colors.dangerEdge, border: 0 },
    secondary: { bg: colors.surface, fg: colors.accent, edge: colors.border, border: 2 },
    ghost: { bg: "transparent", fg: colors.accent, edge: "transparent", border: 0 },
    destructive: { bg: colors.surface, fg: colors.danger, edge: colors.border, border: 2 },
  }[variant];
  const raised = variant !== "ghost" && !inactive;
  const disabledLook = inactive && variant !== "ghost";

  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityHint={accessibilityHint}
      accessibilityState={{ disabled: inactive, busy: loading }}
      disabled={inactive}
      onPress={onPress}
      style={({ pressed }) => {
        const sunk = pressed && raised;
        return [
          styles.base,
          {
            backgroundColor: disabledLook ? colors.idle : look.bg,
            borderColor: disabledLook ? colors.idleEdge : look.edge,
            borderWidth: look.border,
            borderBottomWidth: raised && !sunk ? edge + look.border : look.border,
            marginTop: raised && !sunk ? 0 : edge,
          },
        ];
      }}
    >
      <View style={styles.content}>
        {loading ? <ActivityIndicator color={look.fg} style={styles.spinner} /> : null}
        <Text
          variant="label"
          style={[styles.label, { color: disabledLook ? colors.idleIcon : look.fg }]}
        >
          {label}
        </Text>
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  base: {
    minHeight: touchTarget + 8,
    borderRadius: radius.md,
    paddingHorizontal: spacing.xl,
    justifyContent: "center",
  },
  content: { flexDirection: "row", alignItems: "center", justifyContent: "center" },
  label: { textTransform: "uppercase", letterSpacing: 0.6, fontSize: 15 },
  spinner: { marginRight: spacing.sm },
});
