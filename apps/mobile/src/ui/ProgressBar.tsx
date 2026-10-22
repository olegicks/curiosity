import { StyleSheet, View } from "react-native";

import { useTheme } from "./theme";
import { radius } from "./tokens";

type Props = { value: number; max: number; label: string; height?: number; color?: string };

export function ProgressBar({ value, max, label, height = 8, color }: Props) {
  const { colors } = useTheme();
  const fraction = max > 0 ? Math.min(Math.max(value / max, 0), 1) : 0;
  return (
    <View
      accessibilityRole="progressbar"
      accessibilityLabel={label}
      accessibilityValue={{ min: 0, max, now: value }}
      style={[styles.track, { height, backgroundColor: colors.idle }]}
    >
      <View
        style={[
          styles.fill,
          { width: `${fraction * 100}%`, backgroundColor: color ?? colors.accent },
        ]}
      >
        {height >= 12 && fraction > 0.04 ? <View style={styles.shine} /> : null}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  track: { borderRadius: radius.full, overflow: "hidden", flex: 1 },
  fill: { height: "100%", borderRadius: radius.full, paddingHorizontal: 6, paddingTop: 3 },
  shine: { height: 3, borderRadius: radius.full, backgroundColor: "rgba(255,255,255,0.35)" },
});
