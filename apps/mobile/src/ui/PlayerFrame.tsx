import type { ReactNode } from "react";
import { Pressable, ScrollView, StyleSheet, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { Text } from "./Text";
import { useTheme } from "./theme";
import { readingMaxWidth, spacing, touchTarget } from "./tokens";

/** Full-screen chrome for the lesson and review players: header, scrolling body, footer. */
export function PlayerFrame({
  header,
  footer,
  children,
}: {
  header: ReactNode;
  footer?: ReactNode;
  children: ReactNode;
}) {
  const { colors } = useTheme();
  return (
    <SafeAreaView style={[styles.root, { backgroundColor: colors.bg }]} edges={["top", "bottom"]}>
      <View style={[styles.column, styles.header]}>{header}</View>
      <ScrollView contentContainerStyle={styles.scroll}>
        <View style={styles.column}>{children}</View>
      </ScrollView>
      {footer ? <View style={[styles.column, styles.footer]}>{footer}</View> : null}
    </SafeAreaView>
  );
}

export function HeaderButton({
  label,
  text,
  onPress,
}: {
  label: string;
  text: string;
  onPress: () => void;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      onPress={onPress}
      style={styles.iconButton}
    >
      <Text
        variant={text.length === 1 ? "heading" : "label"}
        tone={text.length === 1 ? "default" : "accent"}
      >
        {text}
      </Text>
    </Pressable>
  );
}

export const playerStyles = StyleSheet.create({ spacer: { flex: 1 } });

const styles = StyleSheet.create({
  root: { flex: 1 },
  column: { width: "100%", maxWidth: readingMaxWidth, alignSelf: "center", gap: spacing.lg },
  header: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
  },
  iconButton: { minWidth: touchTarget, minHeight: touchTarget, justifyContent: "center" },
  scroll: { flexGrow: 1, paddingHorizontal: spacing.lg, paddingVertical: spacing.lg },
  footer: { paddingHorizontal: spacing.lg, paddingBottom: spacing.lg, gap: spacing.sm },
});
