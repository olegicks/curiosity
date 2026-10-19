import type { ReactNode } from "react";
import { RefreshControl, ScrollView, StyleSheet, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { useTheme } from "./theme";
import { readingMaxWidth, spacing } from "./tokens";

type Props = {
  children: ReactNode;
  /** Pinned at the bottom (primary actions), above the safe area. */
  footer?: ReactNode;
  /** Enables pull-to-refresh when provided. */
  onRefresh?: () => void;
  refreshing?: boolean;
};

/** Scrollable page with the app background, readable measure and a fixed action area. */
export function Screen({ children, footer, onRefresh, refreshing = false }: Props) {
  const { colors } = useTheme();
  return (
    <SafeAreaView style={[styles.root, { backgroundColor: colors.bg }]} edges={["top", "bottom"]}>
      <ScrollView
        contentContainerStyle={styles.scroll}
        keyboardShouldPersistTaps="handled"
        refreshControl={
          onRefresh ? (
            <RefreshControl
              refreshing={refreshing}
              onRefresh={onRefresh}
              tintColor={colors.accent}
              colors={[colors.accent]}
            />
          ) : undefined
        }
      >
        <View style={styles.column}>{children}</View>
      </ScrollView>
      {footer ? <View style={[styles.column, styles.footer]}>{footer}</View> : null}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1 },
  scroll: { flexGrow: 1, paddingHorizontal: spacing.lg, paddingVertical: spacing.xl },
  column: { width: "100%", maxWidth: readingMaxWidth, alignSelf: "center", gap: spacing.lg },
  footer: { paddingHorizontal: spacing.lg, paddingBottom: spacing.lg, gap: spacing.sm },
});
