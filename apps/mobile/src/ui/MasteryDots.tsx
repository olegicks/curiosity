import { StyleSheet, View } from "react-native";

import { strings } from "@/i18n/en";

import { useTheme } from "./theme";
import { radius, spacing } from "./tokens";

/** Mastery stage 0-4 as four dots (docs/spec/07 §7.2). */
export function MasteryDots({ stage }: { stage: number }) {
  const { colors } = useTheme();
  return (
    <View
      style={styles.row}
      accessible
      accessibilityRole="image"
      accessibilityLabel={strings.lessons.mastery(stage)}
    >
      {[1, 2, 3, 4].map((i) => (
        <View
          key={i}
          style={[
            styles.dot,
            { borderColor: colors.accent },
            i <= stage && { backgroundColor: colors.accent },
          ]}
        />
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: "row", gap: spacing.xs },
  dot: { width: 8, height: 8, borderRadius: radius.full, borderWidth: 1 },
});
