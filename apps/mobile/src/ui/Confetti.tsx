import { useEffect, useMemo, useState } from "react";
import { Animated, Easing, StyleSheet, useWindowDimensions, View } from "react-native";

import { useReducedMotion } from "@/lib/motion";

const COLORS = ["#6340E0", "#F5A300", "#1A7F45", "#C2410C", "#1F5FD1", "#E64980"];
const PIECES = 36;

/** A one-off confetti burst over the screen. Skipped entirely when motion is reduced. */
export function Confetti() {
  const reduced = useReducedMotion();
  const { width, height } = useWindowDimensions();
  const progress = useState(() => new Animated.Value(0))[0];
  const pieces = useMemo(
    () =>
      Array.from({ length: PIECES }, (_, i) => ({
        x: ((i * 37) % 100) / 100,
        drift: (((i * 53) % 21) - 10) * 6,
        delay: ((i * 29) % 10) / 25,
        spin: ((i * 17) % 4) + 1,
        color: COLORS[i % COLORS.length]!,
        size: 7 + ((i * 11) % 6),
      })),
    [],
  );

  useEffect(() => {
    if (reduced) return;
    const run = Animated.timing(progress, {
      toValue: 1,
      duration: 2200,
      easing: Easing.out(Easing.quad),
      useNativeDriver: true,
    });
    run.start();
    return () => run.stop();
  }, [progress, reduced]);

  if (reduced) return null;
  return (
    <View
      pointerEvents="none"
      style={StyleSheet.absoluteFill}
      importantForAccessibility="no-hide-descendants"
    >
      {pieces.map((p, i) => {
        const start = Math.min(p.delay, 0.5);
        const fall = progress.interpolate({
          inputRange: [0, start, 1],
          outputRange: [-40, -40, height * 0.8],
        });
        const sway = progress.interpolate({ inputRange: [0, 1], outputRange: [0, p.drift] });
        const rotate = progress.interpolate({
          inputRange: [0, 1],
          outputRange: ["0deg", `${p.spin * 360}deg`],
        });
        const opacity = progress.interpolate({ inputRange: [0, 0.8, 1], outputRange: [1, 1, 0] });
        return (
          <Animated.View
            key={i}
            style={[
              styles.piece,
              {
                left: p.x * width,
                width: p.size,
                height: p.size * 1.6,
                backgroundColor: p.color,
                opacity,
                transform: [{ translateY: fall }, { translateX: sway }, { rotate }],
              },
            ]}
          />
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  piece: { position: "absolute", top: 0, borderRadius: 2 },
});
