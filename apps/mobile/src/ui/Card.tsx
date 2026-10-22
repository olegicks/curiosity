import type { ReactNode } from "react";
import { StyleSheet, View } from "react-native";

import { useTheme } from "./theme";
import { radius, spacing } from "./tokens";

type Props = {
  children: ReactNode;
  tone?: "plain" | "muted" | "success" | "danger" | "accent";
};

export function Card({ children, tone = "plain" }: Props) {
  const { colors } = useTheme();
  const look = {
    plain: { bg: colors.surface, border: colors.border },
    muted: { bg: colors.surfaceMuted, border: colors.surfaceMuted },
    success: { bg: colors.successBg, border: colors.success },
    danger: { bg: colors.dangerBg, border: colors.danger },
    accent: { bg: colors.accentBg, border: colors.accentBg },
  }[tone];
  return (
    <View style={[styles.card, { backgroundColor: look.bg, borderColor: look.border }]}>
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    borderWidth: 2,
    borderBottomWidth: 4,
    borderRadius: radius.md,
    padding: spacing.lg,
    gap: spacing.sm,
  },
});
