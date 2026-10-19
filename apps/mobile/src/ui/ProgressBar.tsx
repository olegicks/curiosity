import { StyleSheet, View } from "react-native";

import { useTheme } from "./theme";
import { radius } from "./tokens";

type Props = { value: number; max: number; label: string };

export function ProgressBar({ value, max, label }: Props) {
  const { colors } = useTheme();
  const fraction = max > 0 ? Math.min(Math.max(value / max, 0), 1) : 0;
  return (
    <View
      accessibilityRole="progressbar"
      accessibilityLabel={label}
      accessibilityValue={{ min: 0, max, now: value }}
      style={[styles.track, { backgroundColor: colors.surfaceMuted }]}
    >
      <View
        style={[styles.fill, { width: `${fraction * 100}%`, backgroundColor: colors.accent }]}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  track: { height: 6, borderRadius: radius.full, overflow: "hidden", flex: 1 },
  fill: { height: "100%", borderRadius: radius.full },
});
