import { StyleSheet, View } from "react-native";

import { strings } from "@/i18n/en";

import { Button } from "./Button";
import { Text } from "./Text";
import { useTheme } from "./theme";
import { radius, spacing } from "./tokens";

/** Skeleton placeholder shaped like a list of cards (FR-GLB-1: no bare spinners). */
export function LoadingBlocks({ count = 3 }: { count?: number }) {
  const { colors } = useTheme();
  return (
    <View style={styles.stack} accessibilityLabel="Loading" accessibilityRole="progressbar">
      {Array.from({ length: count }, (_, i) => (
        <View key={i} style={[styles.block, { backgroundColor: colors.surfaceMuted }]} />
      ))}
    </View>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <View style={styles.stack} accessibilityRole="alert">
      <Text>{message}</Text>
      <Button label={strings.lessons.retry} variant="secondary" onPress={onRetry} />
    </View>
  );
}

const styles = StyleSheet.create({
  stack: { gap: spacing.md },
  block: { height: 72, borderRadius: radius.md },
});
