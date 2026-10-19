import { StyleSheet, View } from "react-native";

import { Text } from "./Text";
import { useTheme } from "./theme";
import { radius, spacing } from "./tokens";

type Props = { message: string; tone?: "info" | "error" };

/** Inline, non-blocking message (errors, offline, session notices). */
export function Banner({ message, tone = "info" }: Props) {
  const { colors } = useTheme();
  return (
    <View
      accessibilityRole="alert"
      accessibilityLiveRegion="polite"
      style={[
        styles.banner,
        {
          backgroundColor: tone === "error" ? colors.dangerBg : colors.surfaceMuted,
          borderColor: tone === "error" ? colors.danger : colors.border,
        },
      ]}
    >
      <Text variant="body">{message}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  banner: { borderWidth: 1, borderRadius: radius.md, padding: spacing.md },
});
